import sys, os, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 检查payType=美团 和非空payType的实际数据
for label, file in [('美团', 'learn/paytype_美团.xls'), ('全部', 'learn/paytype_all.xls')]:
    df = pd.read_excel(file, header=None)
    print(f'\n=== {label} ===')
    print(f'Shape: {df.shape}')
    print('Row 0:', df.iloc[0, 0])
    # 统计第3列(费用)中大于0的数量
    fee_col = df.iloc[:, 2]
    non_zero = 0
    for v in fee_col:
        try:
            if float(v) > 0:
                non_zero += 1
        except:
            pass
    print(f'费用>0的行数: {non_zero}')
    print('末2行:')
    print(df.tail(2).to_string())
