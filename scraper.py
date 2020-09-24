import re
import os
import glob

import requests

from typing import Iterable, List
from datetime import datetime

from utils.utils import dir_abs_path_of_file, PrintControl


SHOW_PROGRESS = True
SHOW_NAVIGATION = False
SHOW_REQUESTS = False
SHOW_PARSED_DATA = False


class RequestsDebugger:
    def __init__(self):
        self.session = requests.Session()

    @staticmethod
    def check_response(response):
        print(response)
        print(response.text)

    def get(self, *args, **kwargs):
        response = self.session.get(*args, **kwargs)
        self.check_response(response)
        return response

    def post(self, *args, **kwargs):
        response = self.session.post(*args, **kwargs)
        self.check_response(response)
        return response


class ANMATLab:
    @classmethod
    def header(cls) -> tuple:
        return 'CUIT', 'GLN', 'RAZON_SOCIAL', 'PAGE', 'PAGE_POS'

    @classmethod
    def csv_header(cls) -> str:
        return ','.join(cls.header())

    @classmethod
    def list_to_csv__str(cls, anmat_labs: Iterable['ANMATLab'], header=True):
        csv__str = cls.csv_header() + '\n' if header else ''
        return csv__str + '\n'.join(lab.csv_values() for lab in anmat_labs)

    def __init__(self, cuit, gln, razon_social, page, page_list_pos):
        self.cuit = cuit
        self.gln = gln
        self.razon_social = razon_social
        self.page = page
        self.page_pos = page_list_pos

    def values_sorted_by_header(self) -> tuple:
        return tuple(str(getattr(self, value_name.lower())) for value_name in self.header())

    def csv_values(self) -> str:
        return ','.join(self.values_sorted_by_header())


class ANMATVademecumNavigation:

    URL = 'https://servicios.pami.org.ar/vademecum/views/consultaPublica/listado.zul'
    
    class Control:
        @staticmethod
        def navigation(capture_navigation=True):
            def request_exception_error_handler(method: callable):
                def handler(self: 'ANMATVademecumNavigation', *args, **kwargs):
                    try:
                        response = method(self, *args, **kwargs)
                        if response and "title:'Error'" in response.text:
                            raise requests.exceptions.RequestException
                        return response
                    except requests.exceptions.RequestException:
                        self.reset_connection_and_recover_last_state()
                        return method(self, *args, **kwargs)
                    finally:
                        if capture_navigation:
                            self.capture_navigation(method, args, kwargs)
                return handler
            return request_exception_error_handler

    def __init__(self):
        self.session = None
        self.new_session()
        self.dt_id = None
        self.session_id = None
        self.lab_item_name_in_selector = None
        self.capture_navigation_off = False
        self.print = PrintControl(flush=True, on=SHOW_NAVIGATION)
        self.history_methods = []
        self.history_params = []

    def pass_method(self, *args, **kwargs):
        pass

    def new_session(self):
        self.session = requests.Session() if not SHOW_REQUESTS else RequestsDebugger()

    def capture_navigation(self, method, args, kwargs):
        if self.capture_navigation_off:
            return
        if method in self.history_methods:
            method_pos = self.history_methods.index(method)
            self.history_methods = self.history_methods[:method_pos]
            self.history_params = self.history_params[:method_pos]
        self.history_methods.append(method)
        self.history_params.append((args, kwargs))

    def reset_connection_and_recover_last_state(self):
        self.print.show('[NAVIGATION] --- CONNECTION RESET BY PEER OR RECEIVED ERROR ---')
        self.print.show('[NAVIGATION] --- RE CONNECTING AND STATE RECOVERING ---')
        self.capture_navigation_off = True
        self.new_session()
        for method, params in zip(self.history_methods, self.history_params):
            args, kwargs = params
            method(self, *args, **kwargs)
        self.capture_navigation_off = False

    @Control.navigation()
    def page__open_and_load_session_ids(self):
        self.print.show('[NAVIGATION] --- LOAD MAIN ---')
        main_response = self.session.get(self.URL)
        self.dt_id = re.findall(r'dt:\'([a-z0-9_]+)\'', main_response.text)[0]
        self.session_id = main_response.cookies.get('JSESSIONID')

    def load_labs_pos_and_item_names_in_selector(self, labs_selector_response):
        self.lab_item_name_in_selector = re.findall(
            r"\['zul.sel.Listitem','([^\']+)',{\$\$0onSwipe:true,\$\$0onAfterSize:true,_loaded:true,_index:",
            labs_selector_response.text
        )

    @Control.navigation()
    def labs_selector__open_page(self, page=None):
        def labs_selector__open():
            self.print.show('[NAVIGATION] --- OPEN LABS SELECTOR ---')
            return self.session.post(
                'https://servicios.pami.org.ar/vademecum/zkau;jsessionid={}'.format(self.session_id),
                data={
                  'dtid': self.dt_id,
                  'cmd_0': 'onOpen',
                  'uuid_0': 'zk_comp_40',
                  'data_0': '{"open":true,"value":""}'
                }
            )
        response = labs_selector__open()
        if page:
            self.print.show('[NAVIGATION] --- LABS SELECTOR, SELECT PAGE: {} ---'.format(page))
            response = self.session.post(
                'https://servicios.pami.org.ar/vademecum/zkau',
                data={
                    'dtid': self.dt_id,
                    'cmd_0': 'onPaging',
                    'uuid_0': 'zk_comp_61',
                    'data_0': '{"":1}'.replace('1', str(page))
                }
            )
        self.load_labs_pos_and_item_names_in_selector(response)
        return response

    @Control.navigation()
    def labs_selector__close(self):
        self.print.show('[NAVIGATION] --- CLOSE LABS SELECTOR ---')
        self.session.post(
            'https://servicios.pami.org.ar/vademecum/zkau',
            data={
                'dtid': self.dt_id,
                'cmd_0': 'onClick',
                'uuid_0': 'zk_comp_55',
                'data_0': '{"pageX":506,"pageY":26,"which":1,"x":5,"y":9}'
            }
        )

    @Control.navigation()
    def select_lab_on_selector(self, lab_pos_in_sel):
        self.print.show('[NAVIGATION] --- SELECT LAB {} ON SELECTOR ---'.format(lab_pos_in_sel))
        data_0 = '{"items":["{}"],"reference":"{}","clearFirst":false,' \
                 '"selectAll":false,"pageX":480,"pageY":147,"which":1,"x":242,"y":48}'
        self.session.post(
            'https://servicios.pami.org.ar/vademecum/zkau',
            data={
                'dtid': self.dt_id,
                'cmd_0': 'onSelect',
                'uuid_0': 'zk_comp_56',
                'data_0': data_0.replace('{}', self.lab_item_name_in_selector[lab_pos_in_sel])
            }
        )

    @Control.navigation()
    def search(self):
        self.print.show('[NAVIGATION] --- PRESS SEARCH BUTTON ---')
        data = {
            'dtid': self.dt_id,
            'cmd_0': 'onAnchorPos',
            'uuid_0': 'zk_comp_56',
            'data_0': '{"top":-1,"left":-1}',
            'cmd_1': 'onClick',
            'uuid_1': 'zk_comp_80',
            'data_1': '{"pageX":271,"pageY":289,"which":1,"x":40,"y":23}'
        }
        return self.session.post('https://servicios.pami.org.ar/vademecum/zkau', data=data)

    @Control.navigation()
    def select_meds_list_page(self, page):
        data = {
            'dtid': self.dt_id,
            'cmd_0': 'onPaging',
            'uuid_0': 'zk_comp_99',
            'data_0': '{"":1}'.replace('1', str(page))
        }
        return self.session.post(
            'https://servicios.pami.org.ar/vademecum/zkau;jsessionid={}'.format(self.session_id),
            data=data
        )

    @Control.navigation(capture_navigation=False)
    def open_med_drugs(self, item_name):
        data = {
            'dtid': self.dt_id,
            'cmd_0': 'onClick',
            'uuid_0': item_name,
            'data_0': '{"pageX":1078,"pageY":391,"which":1,"x":53,"y":32}'
        }
        return self.session.post(
            'https://servicios.pami.org.ar/vademecum/zkau',
            data=data
        )


class ANMATScraper:

    URL = 'https://servicios.pami.org.ar/vademecum/views/consultaPublica/listado.zul'

    def __init__(self):
        self.nav = ANMATVademecumNavigation()
        self.data_path = dir_abs_path_of_file(__file__) + 'data/'
        self.labs_path = self.data_path + 'labs/'
        os.makedirs(self.labs_path, exist_ok=True)
        self.labs_amount = None
        self.labs = []  # type: List[ANMATLab]
        self.now = datetime.now()
        self.print = PrintControl(flush=True, on=SHOW_PROGRESS)
        self.print_data = PrintControl(flush=True, on=SHOW_PARSED_DATA)

    def get_how_many_pages_are_in_labs_selector(self):
        labs_selector_response = self.nav.labs_selector__open_page()
        num_pages_labs_sel = int(re.findall(r'"pageCount",([0-9]+)]', labs_selector_response.text)[0])
        self.labs_amount = int(re.findall(r'"totalSize",([0-9]+)]', labs_selector_response.text)[0])
        self.nav.labs_selector__close()
        return num_pages_labs_sel

    def get_how_many_labs_are_in_labs_sel_page(self, page):
        self.nav.labs_selector__open_page(page)
        num_labs_current_page = len(self.nav.lab_item_name_in_selector)
        self.nav.labs_selector__close()
        return num_labs_current_page

    def get_next_lab(self, page):
        response = self.nav.labs_selector__open_page(page)
        item_page_list_pos = 0
        if self.labs and self.labs[-1].page == page:
            item_page_list_pos = self.labs[-1].page_pos + 1
        number_of_values_for_a_lab = 3
        relative_ini_pos = item_page_list_pos * number_of_values_for_a_lab
        relative_end_pos = relative_ini_pos + number_of_values_for_a_lab
        cuit, gln, razon_social = re.findall(r'label:\'([^\']+)\'', response.text)[relative_ini_pos:relative_end_pos]
        self.labs.append(
            ANMATLab(cuit=cuit, gln=gln, razon_social=razon_social, page=page, page_list_pos=item_page_list_pos)
        )

    def update_labs_history_file(self):
        csv_path_names = glob.glob(self.labs_path + "*.csv")
        last_labs__str = None
        if csv_path_names:
            last_csv_path_name = max(csv_path_names)
            with open(last_csv_path_name) as last_labs_csv__file:
                last_labs__str = last_labs_csv__file.read()
        # Not save if not changed
        labs_csv__str = ANMATLab.list_to_csv__str(self.labs)
        if labs_csv__str == last_labs__str:
            return
        with open(self.labs_path + self.now.strftime('%Y%m%d') + '.csv', 'w') as labs_csv__file:
            labs_csv__file.write(labs_csv__str)

    def load_meds_of_the_selected_lab(self):
        def parse_meds_data():
            nonlocal meds_data
            nonlocal lab_meds_re
            meds_cells = re.findall(
                r"',{(visible:false,)?\$\$0onSwipe:true,\$\$0onAfterSize:true(?:(?:,value:')([^\']+)')?}",
                lab_meds_re.text
            )
            new_meds_data = [meds_cells[pos:pos + 14] for pos in range(0, len(meds_cells), 14)]
            meds_drugs_cell = re.findall(
                r"\['zul.wgt.Label','([^']+)',{\$\$0onSwipe:true,\$onClick:true,\$\$0onAfterSize:true,"
                r"style:'cursor:pointer',value:'([^']+)'},\[]]]],",
                lab_meds_re.text
            )
            for pos in range(len(new_meds_data)):
                if pos >= len(meds_drugs_cell):
                    new_meds_data[pos].append(('', ''))
                    new_meds_data[pos].append(('', '[]'))
                    continue
                new_meds_data[pos].append(('', meds_drugs_cell[pos][1]))
                drugs_response = self.nav.open_med_drugs(meds_drugs_cell[pos][0])
                drugs_cells = re.findall(
                    r"',{\$\$0onSwipe:true,\$\$0onAfterSize:true,value:'([^']+)",
                    drugs_response.text
                )
                drugs_table = [drugs_cells[pos:pos+3] for pos in range(0, len(drugs_cells), 3)]
                new_meds_data[pos].append(('', str(drugs_table)))
            for med_data in new_meds_data:
                meds_data.append(tuple(tuple_data[1] if tuple_data[0] == '' else '' for tuple_data in med_data))
        lab_meds_re = self.nav.search()
        pages_re = re.findall(r'"pageCount",([0-9]+)]', lab_meds_re.text)
        if not pages_re or 'La búsqueda no ha devuelto resultados' in lab_meds_re.text:
            return []
        num_pages = int(pages_re[0])
        self.print.show(
            '::: LAB ({}/{}) {} PAGE 1/{} :::'.format(
                len(self.labs), self.labs_amount, self.labs[-1].razon_social, num_pages
            )
        )
        meds_data = []
        parse_meds_data()
        for page in range(1, num_pages):
            self.print.show(
                '::: LAB ({}/{}) {} PAGE {}/{} :::'.format(
                    len(self.labs), self.labs_amount, self.labs[-1].razon_social, page + 1, num_pages
                )
            )
            lab_meds_re = self.nav.select_meds_list_page(page)
            parse_meds_data()
        return meds_data

    def run(self):
        self.nav.page__open_and_load_session_ids()
        labs_sel__num_pages = self.get_how_many_pages_are_in_labs_selector()
        csv_delimiter = '","'
        meds_header__str = '"' + csv_delimiter.join([
            'N° Certificado', 'Laboratorio', 'Nombre Comercial', 'Forma Farmacéutica', 'Presentación',
            'Precio Venta al Público', 'Genérico', 'Detalle',
            ' (uso exclusivamente hospitalario - muestra médica - no venta al público)',
            ' (muestra médica - no venta al público)', ' (uso exclusivamente hospitalario - muestra médica)',
            ' (uso exclusivamente hospitalario - no venta al público)', ' (uso exclusivamente hospitalario)',
            ' (muestra médica)', ' (no venta al público)', 'GTIN', 'Genérico[IFA,Cantidad,Unidad]'
        ]) + '"'
        with open(self.data_path + self.now.strftime('%Y%m%d') + '.csv', 'w') as csv_meds__file:
            csv_meds__file.write(meds_header__str + '\n')
        for labs_sel_pag_num in range(labs_sel__num_pages):
            self.print.show('::: PAGE {}/{} :::'.format(labs_sel_pag_num + 1, labs_sel__num_pages))
            labs_sel_pag__num_labs = self.get_how_many_labs_are_in_labs_sel_page(labs_sel_pag_num)
            for labs_sel_pos in range(labs_sel_pag__num_labs):
                self.get_next_lab(labs_sel_pag_num)
                self.nav.select_lab_on_selector(labs_sel_pos)
                meds = self.load_meds_of_the_selected_lab()
                if not meds:
                    continue
                self.print.show(
                    '::: LAB ({}/{}) {} ENDED WITH {} MEDS PARSED :::'.format(
                        len(self.labs), self.labs_amount, self.labs[-1].razon_social, len(meds)
                    )
                )
                meds_rows = ['"' + csv_delimiter.join(med) + '"' for med in meds]
                csv_meds__str = '\n'.join(meds_rows) + '\n'
                self.print_data.show(csv_meds__str)
                with open(self.data_path + self.now.strftime('%Y%m%d') + '.csv', 'a') as csv_meds__file:
                    csv_meds__file.write(csv_meds__str)
        self.update_labs_history_file()
