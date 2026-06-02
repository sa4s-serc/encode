"""Generate LaTeX ablation table from saved CSV results."""
import pandas as pd
import numpy as np

df_reg = pd.read_csv('c:/Research/EnCoDe/modeling_results/ablation_regression_results.csv')
df_clf = pd.read_csv('c:/Research/EnCoDe/modeling_results/ablation_classification_results.csv')
df = df_reg.merge(
    df_clf[['Configuration', 'Features', 'test_acc', 'test_f1', 'cv_acc_mean', 'cv_acc_std']],
    on=['Configuration', 'Features']
)

full_r2  = df.loc[df['Configuration'] == 'Full Model (all groups)', 'test_r2'].values[0]
full_acc = df.loc[df['Configuration'] == 'Full Model (all groups)', 'test_acc'].values[0]


def fmt_delta_r2(val):
    d = val - full_r2
    if abs(d) < 0.0005:
        return r'\textemdash'
    sign = '+' if d > 0 else ''
    return f'{sign}{d:.3f}'


def fmt_delta_acc(val):
    d = (val - full_acc) * 100
    if abs(d) < 0.05:
        return r'\textemdash'
    sign = '+' if d > 0 else ''
    return f'{sign}{d:.1f}pp'


def make_row(row, bold=False):
    lbl     = str(row['Configuration'])
    n       = int(row['Features'])
    r2      = float(row['test_r2'])
    cv_r2_m = float(row['cv_r2_mean'])
    cv_r2_s = float(row['cv_r2_std'])
    acc     = float(row['test_acc'])
    cv_a_m  = float(row['cv_acc_mean'])
    cv_a_s  = float(row['cv_acc_std'])

    dr = fmt_delta_r2(r2)
    da = fmt_delta_acc(acc)

    cv_reg = f"{cv_r2_m:.3f} $\\pm$ {cv_r2_s:.3f}"
    cv_cls = f"{cv_a_m*100:.1f} $\\pm$ {cv_a_s*100:.1f}"

    if bold:
        r2_cell  = "\\textbf{" + f"{r2:.3f}" + "}"
        acc_cell = "\\textbf{" + f"{acc*100:.1f}\\%" + "}"
        lbl_str  = "\\textbf{" + lbl + "}"
        n_str    = "\\textbf{" + str(n) + "}"
    else:
        r2_cell  = f"{r2:.3f} ({dr})"
        acc_cell = f"{acc*100:.1f}\\% ({da})"
        lbl_str  = lbl
        n_str    = str(n)

    cols = " & ".join([
        "    \\quad " + lbl_str,
        n_str,
        r2_cell,
        cv_reg,
        acc_cell,
        cv_cls + "\\%"
    ])
    return cols + " \\\\"


# ---- Build the table --------------------------------------------------------
rows = []
rows.append(r'\begin{table*}[t]')
rows.append(r'\centering')
caption = (
    r'\caption{Ablation study (XGBoost, best-performing model). '
    r'\textit{Regression}: $R^2$ on log-transformed energy ($\mu$J). '
    r'\textit{Classification}: accuracy for 3-class hotspot tier (Low/Medium/High). '
    r'$\Delta$ = change relative to the full model. '
    r'CV = 5-fold cross-validation mean $\pm$ std. '
    r'Counts and Density feature groups have the largest individual impact '
    r'($-$1.1\% $R^2$ and $-$2.8pp accuracy, respectively), while simple '
    r'size/complexity proxies alone fall far short of the full model.}'
)
rows.append(caption)
rows.append(r'\label{tab:ablation}')
rows.append(r'\setlength{\tabcolsep}{4pt}')
rows.append(r'\begin{tabular}{lc|cc|cc}')
rows.append(r'\toprule')
header1 = (r'  & & \multicolumn{2}{c|}{\textbf{Regression} ($R^2$)} '
           r'& \multicolumn{2}{c}{\textbf{Classification} (Acc)} \\')
rows.append(header1)
header2 = (r'  \textbf{Configuration} & \textbf{\#Feat} '
           r'& \textbf{Test} & \textbf{CV ($\mu \pm \sigma$)} '
           r'& \textbf{Test} & \textbf{CV ($\mu \pm \sigma$)} \\')
rows.append(header2)
rows.append(r'\midrule')

# (a) baselines
rows.append(r'  \multicolumn{6}{l}{\textit{(a) Simple proxy baselines}} \\')
rows.append(r'\midrule')
for lbl in ['Size-only', 'Complexity+Size']:
    rows.append(make_row(df[df['Configuration'] == lbl].iloc[0]))

# (b) full model
rows.append(r'\midrule')
rows.append(r'  \multicolumn{6}{l}{\textit{(b) Full model}} \\')
rows.append(r'\midrule')
rows.append(make_row(df[df['Configuration'] == 'Full Model (all groups)'].iloc[0], bold=True))

# (c) leave-one-group-out
rows.append(r'\midrule')
rows.append(r'  \multicolumn{6}{l}{\textit{(c) Leave-one-group-out (removing each feature group)}} \\')
rows.append(r'\midrule')
for lbl in ['w/o AST Structural', 'w/o Complexity', 'w/o Density',
            'w/o Entropy', 'w/o Counts', 'w/o Halstead']:
    rows.append(make_row(df[df['Configuration'] == lbl].iloc[0]))

# (d) single group only
rows.append(r'\midrule')
rows.append(r'  \multicolumn{6}{l}{\textit{(d) Single-group-only (standalone power)}} \\')
rows.append(r'\midrule')
for lbl in ['Only AST Structural', 'Only Complexity', 'Only Density',
            'Only Entropy', 'Only Counts', 'Only Halstead']:
    rows.append(make_row(df[df['Configuration'] == lbl].iloc[0]))

rows.append(r'\bottomrule')
rows.append(r'\end{tabular}')
rows.append(r'\end{table*}')

latex = '\n'.join(rows) + '\n'

out_path = 'c:/Research/EnCoDe/ablation_table.tex'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(latex)

print("Written:", out_path)
print()
print(latex)
