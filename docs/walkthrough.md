# How the code works

The client asks for information, the server provides it, and the proxy sits between them. Most messages pass through unchanged. For a selected call, the proxy applies the configured fault and records what it did. The [architecture diagram](../README.md#architecture) shows these connections.

## Reading the code

Start with `toy_server.py`. It contains two fictional annual-report pages and a calculator. Then read `policy.py`, which checks the JSON settings and chooses target calls. Calls to other tools do not advance the selected tool's counter.

`injectors.py` contains the actual changes. Each function returns a changed copy or a reason it cannot apply the rule. `evidence.py` writes the events to a log file.

`proxy.py` connects those pieces to the subprocess pipes. It matches replies to request IDs, keeps numeric 1 separate from string `"1"`, and manages delayed replies. Finally, `demo.py` runs the conditions and checks the answers.

## Following one wrong answer

The normal page says revenue rose from 100 to 120. The client asks the calculator for `(120 - 100) / 100 * 100`, which gives 20%.

With semantic corruption enabled, the proxy changes 120 to 150 in the page result. The client now asks for `(150 - 100) / 100 * 100`, which gives 50%. The arithmetic is correct, but the source fact is wrong. The independent checker catches that by checking the two figures as well as the percentage.

Omission causes a different outcome. The page is still a valid string inside a valid result, but the current year's revenue sentence is missing. The client cannot finish its calculation and records an incomplete result.

## Understanding the checks

The direct baseline checks the server and client. The disabled-proxy run checks what happens when the proxy is added without faults. The raw-message test checks that normal bytes survive unchanged; timing can still include process and logging overhead.

Repeatability means the same controlled call numbers are selected with the same settings. Timestamps, process IDs and an LLM's future requests are outside that guarantee.

A selected rule may be skipped if it cannot find the expected text or result shape. The log keeps selection, application and delivery separate so a selected call is not automatically counted as a successful injection.

Cancellation releases the request slot immediately. If a reply is being held, its delay is cancelled. A bounded history suppresses recent cancelled replies that arrive late. Closing the client's input also cancels holds before waiting for the server to stop.

The error fault runs after the real tool has finished. It replaces the reply but cannot undo the tool's actions. The demonstration therefore uses tools without external side effects.

These checks exercise the proxy and a fixed client program. Measuring how LLM agents recover from the same faults would be a separate experiment.
