import sys
path = sys.argv[1] if len(sys.argv) > 1 else 'ChartAnalysis.vue'
lines = open(path, 'r', encoding='utf-8').readlines()

# Fix reload function
for i, l in enumerate(lines):
    if l.strip().startswith('const reload ='):
        lines[i] = "const reload = () => { nextTick(() => { const m = mainTab.value; if (m === 'trend') loadTrend(); else if (m === 'heatmap') loadHeatmap(); else if (m === 'price') loadPrice() }) }\n"
        print(f'Fixed reload at line {i+1}')
        break

# Remove loadWeekday function
start = None
for i, l in enumerate(lines):
    if 'const loadWeekday = async () =>' in l:
        start = i
    if start is not None and i > start and l.strip() == '}' and i - start > 15:
        del lines[start:i+1]
        print(f'Removed lines {start+1}-{i+1}')
        break

open(path, 'w', encoding='utf-8').writelines(lines)
print('Done')
