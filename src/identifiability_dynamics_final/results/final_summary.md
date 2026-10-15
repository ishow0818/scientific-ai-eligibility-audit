# Final validation summary

## Layered verdict

- **Engineering**: `PASS`
- **Local_amplification_mechanism**: `PASS`
- **Theoretical_R_id_threshold**: `PASS`
- **Growth_law_correspondence**: `PASS`
- **Recursion_specificity**: `PASS`
- **Large_N_persistence**: `PASS`
- **Bias_not_required**: `PASS`
- **Bias_selects_direction**: `PASS`
- **Downstream_apparent_uniqueness**: `SUPPORTED`
- **Universal_finite_time_collapse_threshold**: `NOT CLAIMED`
- **revised_core_mechanism**: `PASS`

## Provenance

- **deterministic**: recomputed in this package with frozen F(q) and grids
- **early_stochastic**: recomputed with frozen StochasticGrid (same N,T seeds as verified run)
- **terminal_summaries**: D:\home\Identifiability\outputs\pilot_alt_dynamics

## Deterministic local threshold

| R_range     |   median_lambda_emp |   sign_match_rate |   n |
|:------------|--------------------:|------------------:|----:|
| R<=0.95     |           -0.328502 |           1       | 210 |
| 0.95<R<1.05 |            0        |           0.97619 |  42 |
| R>=1.05     |            0.281136 |           1       | 144 |

## Threshold alignment

|   mu |   theory_alpha_c |   empirical_crossing_lo |   empirical_crossing_hi | status     | aligned   |
|-----:|-----------------:|------------------------:|------------------------:|:-----------|:----------|
| 0    |          1       |                    1    |                     1   | EXACT_GRID | True      |
| 0.05 |          1.05263 |                    1.05 |                     1.1 | INTERVAL   | True      |
| 0.1  |          1.11111 |                    1.1  |                     1.2 | INTERVAL   | True      |
| 0.2  |          1.25    |                    1.2  |                     1.3 | INTERVAL   | True      |
| 0.3  |          1.42857 |                    1.3  |                     1.5 | INTERVAL   | True      |
| 0.4  |          1.66667 |                    1.5  |                     1.8 | INTERVAL   | True      |

## Growth law

| subset        |   n |   pearson_r |   spearman_rho |         MAE |        RMSE |
|:--------------|----:|------------:|---------------:|------------:|------------:|
| epsilon=0.001 |  84 |           1 |       0.999392 | 1.86646e-06 | 4.47841e-06 |
| epsilon=0.002 |  84 |           1 |       0.999382 | 7.46487e-06 | 1.79097e-05 |
| epsilon=0.005 |  84 |           1 |       0.999362 | 4.66122e-05 | 0.000111764 |
| pooled        | 252 |           1 |       0.999233 | 1.86479e-05 | 6.54015e-05 |

## Recursive vs No-recursion

| R_bin     |   A10_Rec |   A10_NR |   Amp_excess |   Pcollapse_Rec |   Pcollapse_NR |   H_T_Rec |   H_T_NR |
|:----------|----------:|---------:|-------------:|----------------:|---------------:|----------:|---------:|
| R<=0.9    |   1.43492 | 0.956695 |     0.473132 |           0     |              0 |  0.992774 | 0.997402 |
| 0.9<R<1.2 |   3.27267 | 0.968519 |     2.27331  |           0.027 |              0 |  0.880947 | 0.995378 |
| R>=1.2    |   9.39402 | 0.94487  |     8.45063  |           0.991 |              0 |  0.264345 | 0.995378 |

## Large-N control

|    N |   D10_rec |   D10_nr |   Amplification_excess_10 | ok   |   terminal_Pcollapse_rec |   terminal_Pcollapse_nr |
|-----:|----------:|---------:|--------------------------:|:-----|-------------------------:|------------------------:|
|   20 |  0.3109   | 0.0877   |                   2.75216 | True |                    0.536 |                       0 |
|   50 |  0.26312  | 0.05712  |                   3.97991 | True |                    0.496 |                       0 |
|  100 |  0.21582  | 0.03938  |                   4.3394  | True |                    0.554 |                       0 |
|  500 |  0.132444 | 0.016716 |                   6.5665  | True |                    0.558 |                       0 |
| 2000 |  0.065814 | 0.008713 |                   6.66678 | True |                    0.652 |                       0 |
