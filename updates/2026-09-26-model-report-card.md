# Our model lost to the baseline, so we ship the baseline

We trained a LightGBM model to predict the 1-in-100 bad case for every stock and every closed
period, and tested it only on years it never saw (2017 to 2026, 1.2 million closed periods).
It beat two of our three baselines. It did not beat the third: each stock's recent volatility,
scaled by how long the market is closed, then calibrated separately for earnings nights,
weekends, holidays and overnights.

So Afterhours uses that baseline, and the report card says so in its first sentence. It is well
calibrated where it matters most: on earnings nights, 1.08% of opens fell below the predicted
1-in-100 bad case. We kept every variant we tried in the repo.
