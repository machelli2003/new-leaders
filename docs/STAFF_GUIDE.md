# Staff guide

**Roles:** Super Admin (platform owner, hidden from hotel staff), Hotel Admin (everything for the hotel), Hotel Manager (operations, reservations, refunds view, reports), Receptionist (bookings, guests, payments at the desk, check-in/out, housekeeping view).

## Daily
- **Front desk → Check-in/out:** see arrivals, departures, in-house. Check in only after verifying ID. Overrides (early, unpaid, room not ready) need manager permission and are logged.
- **Reservations → New:** walk-in/phone bookings. Choose dates, rooms (or auto-assign), guest. "Pending" holds the room for the configured minutes.
- **Record payment** on the reservation for cash/MoMo/POS/transfer; a receipt number is issued.
- **Housekeeping:** rooms go dirty on check-out; mark cleaning → clean → inspection → ready.
- **Maintenance:** create a request and block rooms for dates; blocked rooms disappear from availability.

## Money
- Online payments are confirmed only by server-side Paystack verification/webhook. Use **Payments → Re-verify** if a payment looks stuck.
- If a guest pays after their hold expired, the system re-secures the rooms if free; otherwise the reservation is flagged **Needs attention** and a refund request is created. Review it the same day.
- **Refunds are never automatic:** request → approve → process (online refunds go through Paystack; cash refunds are recorded manually).

## Website
Website content → edit a section → Save draft → Preview site → Save & publish. Add only real information and photos. Testimonials must be real and marked verified.

## Security
Change the temporary password at first sign in. Use strong unique passwords. Staff accounts lock after 5 failed sign-ins. Hotel Admin can disable accounts and reset passwords.
