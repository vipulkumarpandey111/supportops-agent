# Cloudnest Account Access Troubleshooting

## Password Reset Issues
If a customer resets their password but still can't log in, the most common
cause is a cached session on another device auto-retrying the old password
and triggering a temporary lockout. Advise the customer to wait 15 minutes
after a reset before trying again, and to log out of all other devices from
the "Manage Devices" page first.

## Account Lockouts
After 5 failed login attempts, an account is locked for 30 minutes as a
security measure. Support agents can manually clear a lockout early only
after verifying the customer's identity via their registered email.

## Two-Factor Authentication (2FA) Recovery
If a customer has lost access to their 2FA device, they must verify their
identity via their registered recovery email before 2FA can be disabled by
support. Never disable 2FA based on a support ticket alone without this
verification step.

## Email Change Requests
Changing the account's registered email requires confirming the change link
sent to both the old and new email addresses, to prevent account takeover.
