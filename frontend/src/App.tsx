import type React from 'react'
import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/lib/auth'
import { PublicLayout } from '@/public/Layout'
import Home from '@/public/Home'
import { About, Rooms, RoomDetail, Facilities, Restaurant, Events, Gallery, Offers, Contact, FAQ, Policy } from '@/public/Pages'
import { BookingSearch, Checkout, BookingLookup, BookingManage, GuestPasswordReset, PaymentSuccess, PaymentFailed } from '@/public/Booking'
import { EventBooking } from '@/public/EventBooking'
import { BookingHub } from '@/public/BookingHub'

const L = (f: () => Promise<any>, n: string): React.ComponentType<any> => lazy(() => f().then((m) => ({ default: m[n] })))
const Login = L(() => import('@/admin/Auth'), 'Login')
const ChangePassword = L(() => import('@/admin/Auth'), 'ChangePassword')
const MfaEnrollment = L(() => import('@/admin/Auth'), 'MfaEnrollment')
const AdminLayout = L(() => import('@/admin/Layout'), 'AdminLayout')
const Dashboard = L(() => import('@/admin/Dashboard'), 'Dashboard')
const Reservations = L(() => import('@/admin/Reservations'), 'Reservations')
const ReservationDetail = L(() => import('@/admin/Reservations'), 'ReservationDetail')
const NewReservation = L(() => import('@/admin/Reservations'), 'NewReservation')
const PrintReservation = L(() => import('@/admin/Reservations'), 'PrintReservation')
const CalendarPage = L(() => import('@/admin/Rooms'), 'CalendarPage')
const RoomsAdmin = L(() => import('@/admin/Rooms'), 'RoomsAdmin')
const EventVenuesAdmin = L(() => import('@/admin/EventVenues'), 'EventVenuesAdmin')
const EventBookingsAdmin = L(() => import('@/admin/EventVenues'), 'EventBookingsAdmin')
const Guests = L(() => import('@/admin/Finance'), 'Guests')
const Payments = L(() => import('@/admin/Finance'), 'Payments')
const Refunds = L(() => import('@/admin/Finance'), 'Refunds')
const Reports = L(() => import('@/admin/Finance'), 'Reports')
const Pricing = L(() => import('@/admin/Pricing'), 'Pricing')
const FrontDesk = L(() => import('@/admin/Operations'), 'FrontDesk')
const Housekeeping = L(() => import('@/admin/Operations'), 'Housekeeping')
const Maintenance = L(() => import('@/admin/Operations'), 'Maintenance')
const Website = L(() => import('@/admin/Website'), 'Website')
const MediaLibrary = L(() => import('@/admin/Media'), 'MediaLibrary')
const Staff = L(() => import('@/admin/System'), 'Staff')
const AuditLogs = L(() => import('@/admin/System'), 'AuditLogs')
const Settings = L(() => import('@/admin/System'), 'Settings')
const SuperDashboard = L(() => import('@/super/Super'), 'SuperDashboard')
const Wizard = L(() => import('@/super/Super'), 'Wizard')

const P = (path: string, el: JSX.Element, perm?: string) => <Route path={path} element={<RequireAuth perm={perm}>{el}</RequireAuth>} />

export default function App() {
  return (
    <Suspense fallback={null}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Home />} />
          <Route path="book" element={<BookingHub />} />
          <Route path="about" element={<About />} />
          <Route path="rooms" element={<Rooms />} />
          <Route path="rooms/:slug" element={<RoomDetail />} />
          <Route path="facilities" element={<Facilities />} />
          <Route path="restaurant" element={<Restaurant />} />
          <Route path="events" element={<Events />} />
          <Route path="events/book" element={<EventBooking />} />
          <Route path="gallery" element={<Gallery />} />
          <Route path="offers" element={<Offers />} />
          <Route path="contact" element={<Contact />} />
          <Route path="faq" element={<FAQ />} />
          <Route path="privacy-policy" element={<Policy kind="privacy" />} />
          <Route path="terms" element={<Policy kind="terms" />} />
          <Route path="cancellation-policy" element={<Policy kind="cancellation" />} />
          <Route path="booking/search" element={<BookingSearch />} />
          <Route path="booking/checkout" element={<Checkout />} />
          <Route path="booking/lookup" element={<BookingLookup />} />
          <Route path="booking/password-reset" element={<GuestPasswordReset />} />
          <Route path="booking/payment/success" element={<PaymentSuccess />} />
          <Route path="booking/payment/failed" element={<PaymentFailed />} />
          <Route path="booking/:reference" element={<BookingManage />} />
        </Route>
        <Route path="/admin/login" element={<Login />} />
        <Route path="/super-admin/login" element={<Login superAdmin />} />
        <Route path="/admin/change-password" element={<RequireAuth><ChangePassword /></RequireAuth>} />
        <Route path="/super-admin/mfa-setup" element={<RequireAuth superAdmin><MfaEnrollment /></RequireAuth>} />
        <Route path="/admin/reservations/:id/print" element={<RequireAuth perm="reservations.view"><PrintReservation /></RequireAuth>} />
        <Route path="/admin" element={<RequireAuth><AdminLayout /></RequireAuth>}>
          <Route index element={<Navigate to="dashboard" replace />} />
          {P('dashboard', <Dashboard />, 'dashboard.view')}
          {P('reservations', <Reservations />, 'reservations.view')}
          {P('reservations/new', <NewReservation />, 'reservations.create')}
          {P('reservations/:id', <ReservationDetail />, 'reservations.view')}
          {P('calendar', <CalendarPage />, 'availability.view')}
          {P('rooms', <RoomsAdmin />, 'rooms.view')}
          {P('event-venues', <EventVenuesAdmin />, 'rooms.view')}
          {P('event-bookings', <EventBookingsAdmin />, 'reservations.view')}
          {P('front-desk', <FrontDesk />, 'checkin.manage')}
          {P('housekeeping', <Housekeeping />, 'housekeeping.view')}
          {P('maintenance', <Maintenance />, 'maintenance.manage')}
          {P('guests', <Guests />, 'guests.view')}
          {P('payments', <Payments />, 'payments.view')}
          {P('refunds', <Refunds />, 'refunds.view')}
          {P('pricing', <Pricing />, 'pricing.manage')}
          {P('reports', <Reports />, 'reports.operational')}
          {P('website', <Website />, 'website.manage')}
          {P('media', <MediaLibrary />, 'media.manage')}
          {P('staff', <Staff />, 'staff.manage')}
          {P('audit-logs', <AuditLogs />, 'audit.view')}
          {P('settings', <Settings />, 'hotel.manage')}
        </Route>
        <Route path="/super-admin" element={<RequireAuth superAdmin><AdminLayout superAdmin /></RequireAuth>}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<SuperDashboard />} />
          <Route path="setup" element={<Wizard />} />
          <Route path="logs" element={<AuditLogs />} />
        </Route>
        <Route path="*" element={<div className="p-20 text-center"><h1 className="text-4xl">Page not found</h1><a className="underline" href="/">Home</a></div>} />
      </Routes>
    </Suspense>
  )
}
