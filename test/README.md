# Unit testing

Quick testing overview:

There are two kinds of tests implemented for this service seed: unit & integration (or end-to-end&mdash;e2e).
Unit tests are for application logic & I tend to test only the functional parts that require little (or no) stubbing to make work.
To this end, I try to write my code in as functional (or Faux-O, to steal a phrase from Gary Bernhardt's talk, [*Boundaries*](https://www.destroyallsoftware.com/talks/boundaries)) of a style as possible.

Tests live in two places: unit tests in this directory built alongside the application, & integration tests outside the application designed to interface with it as any user would:

```
.
├── src/...             # application source lives here
└── test
    ├── integration
    │   ├── helpers/... # integration test helpers
    │   └── ...         # integration tests live here
    └── unit
        ├── helpers/... # unit test helpers
        └── ...         # unit tests live here
```

## What to test here

Test the code that your worker routes rely on.
Ideally, this means you'll define your application logic as separate modules that live next to `./app/src/server.py`, then import the necessary functions & use them in your route definitions.
By doing it this way, your application logic can rely on definable, & thus testable, inputs & outputs.

The examples included already are very trivial, but you'll see that they are testing functions that live at `./app/src/lib.py` & not anything at `./app/src/server.py`.
As a result, these tests don't care about AMQP workers, database connections, or logging output at all, allowing us to test only the arguments passed into a function & the value returned from it.

## What not to test here

Don't test the routes themselves.
Instead, write integration tests for each route in `./integration-tests/tests/`.
