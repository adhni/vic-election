# Change since last election

In the U.S. explorer's Demographics view, choose **Chart → Change since last election**. A hollow dot shows the previous election share and a filled dot shows the current share, connected on a common percentage axis. Each row shows the actual election years, both shares and percentage-point change. An outlined current dot marks a party flip. Blue/red lines mean movement toward Democrats/Republicans; changes below half a point are grey. Party selection changes the shares, while movement colours keep the map's meaning.

The chart uses the same eligible election comparisons as the existing swing view, across House, presidential, Senate and supported governor cycles. Governor baselines follow each state's two-/four-year cycle; Senate baselines follow the regular seat's six-year cycle. Excluded areas remain available through selection and results, with the existing explanations. Provisional results and boundary/count limitations still apply.

Show all comparable areas when there are at most 20. Otherwise show the largest absolute swings, with the selected eligible area pinned first and up to 19 other areas. Ties sort by area name. The note states this display limit; it is not a national average or a representative sample. Sample selection applies before ranking. This chart needs election shares, so missing demographic values alone do not exclude an area. Demographic correlations are hidden, and returning to the demographics chart restores its metric-based sample.

Click a row or use the area selector/map to select an area. Keyboard users can Tab through rows, use Up/Down/Home/End to move, and Enter/Space to select. The party and full/fit share-axis controls apply to both endpoints. The choice survives reload and shared URLs through `demographicChart=before-after`.

Browser validation: `.venv/bin/python scripts/test_before_after_ux.py`. It checks source shares and years, flip markers, selected-area pinning, party inversion, axes, keyboard selection, URL reload, mobile layout and restoration of the demographic scatter across all four election families.
