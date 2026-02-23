The output data used from the collection and declustering CLI commands were used in an external data analysis testing suite and found that the G-K declustering window currently implemented may work however the determining spatial and temporal parameters could be too large. Please review the following statement from the data analysis report, "G-K Classification Confidence" section:

>"Several methodological considerations bear on this finding. First, the G-K algorithm applies a deterministic window: any event inside the window is classified as an aftershock of the parent, with no probability weighting. The confidence assessment here asks a symmetric question (how many mainshocks are inside another mainshock's window), which does not directly replicate the original declustering procedure but does identify events where the classification boundary is uncertain. Second, the magnitude range of this catalog (M≥6.0) means that G-K windows are large: the M6.0 window is approximately 211 km and 220 days. In a global catalog with sustained seismic activity in dense fault zones (Japan, Indonesia, the Aleutians), a large fraction of events will inevitably lie within one another's windows regardless of causal independence. Third, the Nandan et al. (2024) comparison uses ETAS independence probabilities, which are a distinct (and arguably more physically grounded) measure of independence than the G-K window test used here; the threshold comparison should be interpreted as approximate context rather than a direct equivalence."

Here is the simple population overview produced from the data analysis:
| Population   | n     | Date Range Start     | Date Range End       |
| ------------ | ----- | -------------------- | -------------------- |
| Full catalog | 9,802 | 1949-12-25T22:40:40Z | 2021-12-19T16:28:22Z |
| Mainshocks   | 6,222 | 1949-12-25T22:40:40Z | 2021-12-19T16:28:22Z |
| Aftershocks  | 3,580 | 1949-12-25T23:17:31Z | 2021-12-16T21:14:46Z |

I would like to conduct a "due diligence" review of the declustering feature. Given this review please make a plan to:
1) the @tests/test_decluster.py to ensure that they accurately assert the Gardner-Knopoff (1974) algorithm
2) Tests edge cases, like high/low latitude coordinates where spatial proximity will be closer than at the equator, and still meet the window parameters
3) Using @data/output/global_events_pre-review.csv create a declustered set mainshock.csv and aftershock.csv and test that they match the above "population overview" table metrics
4) Make a determination on if the large window is due to the nature of the Gardner-Knopoff (1974) algorithm itself or something that needs to be addressed in our implementation