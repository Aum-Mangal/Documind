Post-incident review: customer payments outage, 14 March 2026

On 14 March 2026 the customer billing portal could not take card payments for 2 hours and 47 minutes, from 09:12 to 11:59 UTC. During this window 1,318 payment attempts failed. No payments were taken twice and no card data was exposed. This review follows the blameless format: it describes what happened and what we will change, not who was at fault.

Severity was rated SEV-2: a customer-facing feature was unavailable, but invoices could still be paid by bank transfer.
<<<PAGE>>>
Timeline (UTC)

08:55 — A scheduled renewal of the TLS certificate for the internal payments gateway completes.
09:12 — The billing portal starts returning errors for card payments. The error rate alert does not fire because the alert threshold was set to 50 percent over ten minutes.
09:41 — A customer contacts support. Support opens an incident.
10:05 — The on-call engineer, Ricardo Alves, identifies certificate validation failures in the gateway logs.
11:20 — The cause is confirmed: the new certificate was issued without the intermediate certificate in the chain.
11:52 — A corrected certificate bundle is deployed.
11:59 — Card payments succeed again. Monitoring confirms recovery.
<<<PAGE>>>
Root cause and contributing factors

The root cause was an incomplete certificate chain. The renewal script requested a certificate from the new certificate authority introduced in February, which returns the leaf certificate and the intermediate certificate as separate files. The script only installed the first file.

Contributing factors: the renewal was not tested against a staging gateway; the error-rate alert threshold was too high to detect a total failure of one payment method; and the runbook for the payments gateway did not mention certificate problems, which slowed diagnosis by about an hour.
<<<PAGE>>>
Actions

1. Install the full certificate chain and validate it automatically after every renewal, failing the renewal if validation fails. Owner: Ricardo Alves. Due 31 March. Done.
2. Lower the payment error-rate alert to 5 percent over five minutes, per payment method. Owner: Sofia Marques. Due 31 March. Done.
3. Run certificate renewals against the staging gateway first. Owner: platform team. Due 30 April.
4. Add certificate failures to the payments runbook. Owner: Ricardo Alves. Due 15 April.

Affected customers were emailed on 15 March. Late-payment fees for invoices due on 14 March were waived.
