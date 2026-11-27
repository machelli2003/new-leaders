import { Link } from 'react-router-dom'
import { ArrowRight, CalendarDays, Clock3, Users } from 'lucide-react'
import { Img } from '@/components/Img'
import { Seo } from '@/components/Seo'
import { Button } from '@/components/ui/button'
import { useEventVenues, useRooms } from './data'
import { Container, PageHero } from './Parts'

export function BookingHub() {
  const rooms = useRooms()
  const venues = useEventVenues()
  const roomImage = rooms.data?.[0]?.main_image
  const venueImage = venues.data?.[0]?.main_image

  return (<><Seo title="Book a stay or event" path="/book" /><PageHero title="What would you like to book?" sub="Choose a room for your stay or a venue for your event." />
    <Container className="py-12 sm:py-16">
      <div className="grid gap-6 lg:grid-cols-2">
        <article className="overflow-hidden rounded-2xl border border-sand bg-white shadow-sm">
          <Img media={roomImage} className="aspect-[16/9] w-full" label="Rooms and suites" />
          <div className="space-y-5 p-6 sm:p-8">
            <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-600">Accommodation</p>
              <h2 className="mt-2 font-serif text-3xl font-semibold text-forest-800">Book a stay</h2>
              <p className="mt-3 text-sm leading-relaxed text-[#4b5750]">Find a room or suite for your visit. Search by check-in and check-out dates, then choose the rooms that suit your group.</p>
            </div>
            <div className="flex flex-wrap gap-4 text-xs text-[#5b665f]"><span className="inline-flex items-center gap-1.5"><CalendarDays className="h-4 w-4 text-gold-600" />Overnight dates</span><span className="inline-flex items-center gap-1.5"><Users className="h-4 w-4 text-gold-600" />Guest and room counts</span></div>
            <Button asChild variant="gold" size="lg" className="w-full sm:w-auto"><Link to="/booking/search">Find a room <ArrowRight className="h-4 w-4" /></Link></Button>
          </div>
        </article>

        <article className="overflow-hidden rounded-2xl border border-sand bg-white shadow-sm">
          <Img media={venueImage} className="aspect-[16/9] w-full" label="Event venue" />
          <div className="space-y-5 p-6 sm:p-8">
            <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold-600">Celebrations & meetings</p>
              <h2 className="mt-2 font-serif text-3xl font-semibold text-forest-800">Book an event venue</h2>
              <p className="mt-3 text-sm leading-relaxed text-[#4b5750]">Choose a conference room or event centre for an engagement, wedding, party, conference or other occasion.</p>
            </div>
            <div className="flex flex-wrap gap-4 text-xs text-[#5b665f]"><span className="inline-flex items-center gap-1.5"><CalendarDays className="h-4 w-4 text-gold-600" />Choose your event date</span><span className="inline-flex items-center gap-1.5"><Clock3 className="h-4 w-4 text-gold-600" />Book by the hour</span><span className="inline-flex items-center gap-1.5"><Users className="h-4 w-4 text-gold-600" />Capacity checked</span></div>
            {venues.isError && <p role="status" className="text-xs text-[#7a847e]">Venue photos and availability are temporarily unavailable. You can still open the event booking flow.</p>}
            <Button asChild variant="gold" size="lg" className="w-full sm:w-auto"><Link to="/events/book">Choose a venue <ArrowRight className="h-4 w-4" /></Link></Button>
          </div>
        </article>
      </div>
      <p className="mt-8 text-center text-sm text-[#5b665f]">Manage bookings with your reference and email or WhatsApp number. <Link className="font-medium text-forest-800 underline underline-offset-2 hover:text-gold-700" to="/booking/lookup">Find an existing booking</Link></p>
    </Container>
  </>)
}
