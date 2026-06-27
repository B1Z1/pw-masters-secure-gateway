#table(
  columns: 5,
  table.header[Kanał][p50 (ms)][p90 (ms)][p99 (ms)][n],
  [deanonymization][4.03][4.829][5.151][56],
  [depseudonymize][4.775][6.418][7.566][56],
  [detect][68.084][82.628][146.571][56],
  [fake_generation][9.061][10.821][11.465][56],
  [llm_request][0.01][0.014][0.021][56],
  [ner_analysis][65.043][78.231][80.303][56],
  [pseudonymize][83.448][100.327][107.231][56],
  [redis_write][7.358][8.711][9.713][56],
  [total][85.01][102.133][105.99][56],
)
