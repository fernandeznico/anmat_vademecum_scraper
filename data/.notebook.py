import pandas as pd

sep = pd.read_csv('20200916.csv')

dic = pd.read_csv('20201223.csv')

sep = sep[[' (muestra médica)', 'Precio Venta al Público']]

dic = dic[[' (muestra médica)', 'Precio Venta al Público']]

sep.rename(columns={' (muestra médica)': 'id', 'Precio Venta al Público': 'precio'}, inplace=True)

dic.rename(columns={' (muestra médica)': 'id', 'Precio Venta al Público': 'precio'}, inplace=True)

j = sep.merge(dic, how='outer', left_on=['id'], right_on=['id'], suffixes=['_sep', '_dic'])

a = j.dropna()
