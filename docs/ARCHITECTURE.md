# Architecture notes
- **Database:** MongoDB stores document-shaped application records. Collection indexes enforce uniqueness and query performance.
- **Double-booking prevention:** `room_nights` has one record per physical room per night with `_id = "<room_id>|<date>"`. MongoDB's unique `_id` prevents concurrent reservations/holds/blocks from owning the same room-night. Check-out date is never inserted, so same-day turnover works naturally. Holds carry `hold_expires_at`; expired holds count as free.
- **Dates:** stay dates are `YYYY-MM-DD` strings in hotel time (Africa/Accra); the check-out date is not an occupied night. Timestamps are UTC.
- **Money:** integer pesewas (minor units) everywhere; GHS only. Prices are snapshotted on the reservation (`pricing`, `pricing_history`).
- **Payments:** reservation status and payment status are separate. Settlement is idempotent (`pending → success` via atomic update + unique reference), amount/currency are checked, webhooks are HMAC-SHA512 verified.
- **Pricing precedence:** rule type (date > holiday > seasonal > weekend), then specificity (room > category > global), then priority; fallback room override, then category default. Taxes are configurable in basis points and empty by default.
- **Auth:** 15-minute JWT access token (kept in memory), rotating refresh token (hashed, httpOnly SameSite=Strict cookie), lockout, `token_version` to revoke sessions, optional TOTP for Super Admin. All permission checks are server-side.
- **Media:** validated by content (JPEG/PNG/WEBP; SVG rejected), webp variants generated, usage checked before delete.
- **Audit:** append-only, secrets scrubbed; Super Admin activity hidden from hotel staff except `support.*` actions.
