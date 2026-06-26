#table(
  columns: 5,
  table.header[Kanał][p50 (ms)][p90 (ms)][p99 (ms)][n],
  [deanonymization][4.222][5.043][5.527][56],
  [depseudonymize][5.104][5.798][6.541][56],
  [detect][64.345][76.986][88.639][56],
  [fake_generation][9.128][10.044][12.368][56],
  [llm_request][0.009][0.01][0.015][56],
  [ner_analysis][62.219][75.263][79.238][56],
  [pseudonymize][77.844][92.103][95.579][56],
  [redis_write][7.047][7.792][10.096][56],
  [total][82.504][97.679][102.773][56],
)
