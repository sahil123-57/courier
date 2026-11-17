# Courier

Parcel booking, scanning and tracking on Frappe.

## Setup

    bench get-app /path/to/courier_app
    bench --site mysite.local install-app courier

Add these to `sites/mysite.local/site_config.json`:

    "courier_secret": "some-long-random-string",
    "razorpay_key_id": "rzp_test_xxx",
    "razorpay_key_secret": "xxx",
    "razorpay_webhook_secret": "xxx"

In the Razorpay dashboard, point the webhook (events `payment.captured` and `order.paid`) to
`https://<your-site>/api/method/courier.api.razorpay_webhook`.

## Setting up data (Desk)

1. Create a Hub for each city (one hub per city).
2. Create Shipping Rates for each city pair and service level.
3. Create a user for each agent, give the role `Delivery Agent`, then add a Delivery Agent record with their hub.
4. Customers sign up on the site and get the role `Courier Customer`.

## Run the tests

    bench --site mysite.local run-tests --app courier

The state machine and token tests do not need Frappe:

    python -m unittest courier.tests.test_state_machine

## Pages

- `/scan` is the agent scanner (needs HTTPS for the camera).
- `frontend/` has the customer pages (Frappe UI). Create the app with
  `npx degit frappe/frappe-ui-starter frontend`, then copy `src/pages` and `src/router.js` into it.

## How a scan works

`courier/scan.py` has `process_scan`. The rules table lives in `courier/state_machine.py`.
