# CRISP-DM phase 1 — Business understanding

## The problem

A rider standing on a New York sidewalk wants to know one thing before they get
in a cab: **when will I actually arrive, and what will it cost?** A dispatcher
and a fleet operator want the same number for different reasons — matching
supply to demand, and quoting honestly.

"About 20 minutes" is not a useful answer to that question. A trip from Midtown
to JFK takes 30 minutes at 4am and 71 minutes at 5pm. The average of those is
wrong at both times of day.

## Objectives

**Business objective.** Give a rider an arrival time they can plan around, with
an honest statement of how uncertain it is, plus the fare they should expect on
the meter.

**Data-mining objective.** Predict trip duration in seconds from information
available *at the moment of booking* — pickup point, dropoff point, departure
time, party size. Nothing observed during or after the trip may be used.

That constraint does real work. It rules out the trip distance recorded by the
meter, the actual dropoff time, and the fare — all of which are in the source
data and all of which would leak the answer.

## Success criteria

| Criterion | Target | Why this one |
|---|---|---|
| RMSLE | Beat every baseline on a time-based split | The competition metric, and the right one — see below |
| MAE | Single-digit minutes | The error a rider actually feels |
| Interval coverage | P10–P90 contains the truth ~80% of the time | An uncertainty band nobody has checked is decoration |
| Latency | Interactive (sub-second per request) | It sits behind a map that updates as pins are dragged |
| Reproducibility | One command, from raw data to running app | Coursework that cannot be rerun cannot be graded |

## Why RMSLE is the headline metric

Trip durations span two orders of magnitude — a three-minute hop across
Midtown and a ninety-minute crawl to the airport are both ordinary. Plain RMSE
would let the model buy accuracy on airport runs by being sloppy on short
trips, because a 5-minute error on a 90-minute trip and a 5-minute error on a
6-minute trip contribute equally.

RMSLE scores the **ratio** instead of the difference. Being 80% wrong is
equally bad whether the trip is short or long, which matches how a rider
experiences the error. It is also the metric the Kaggle competition scores, so
the numbers here are comparable to a public leaderboard.

MAE in seconds is reported alongside it, because RMSLE is not something you can
feel and "typically wrong by about 3 minutes" is.

## Scope and honest limits

- **New York yellow cabs only.** Not for-hire vehicles, not other cities.
- **The fare is computed, not learned.** The TLC rate card is a published
  deterministic schedule. Fitting a model to it would add error and hide where
  the money goes. See `src/nyctaxi/fare.py`.
- **Route geometry is display only.** The map draws a real road route from
  OSRM, but the model never sees it — calling a routing service once per row is
  infeasible at training time, and a feature available at serving but not at
  training is a silent correctness bug. See the note in `src/nyctaxi/api/routing.py`.
- **Traffic, weather and events are not modelled.** The model learns the
  *typical* conditions for a time and place, not today's accident on the BQE.
  This is the single largest source of irreducible error, and it is exactly
  what the P10–P90 band is there to communicate.

## Deliverable

A single deployable artifact: one FastAPI process serving both the JSON API and
an interactive map interface, backed by a versioned model whose evaluation
report is readable in the browser.

→ Next: [Data understanding](02-data-understanding.md)
