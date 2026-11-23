/** Field definitions for CMS sections. The admin editor renders forms from these; public pages read the same keys. */
export type FieldDef = { name: string; label: string; type: 'text' | 'textarea' | 'media' | 'medias' | 'list' | 'money'; hint?: string; fields?: FieldDef[] }
export type SectionDef = { key: string; label: string; group: string; fields: FieldDef[] }

export const SECTIONS: SectionDef[] = [
  { key: 'home.hero', label: 'Homepage banner', group: 'Homepage', fields: [
    { name: 'headline', label: 'Headline', type: 'text' }, { name: 'subheadline', label: 'Sub-headline', type: 'textarea' },
    { name: 'cta_label', label: 'Button label', type: 'text', hint: 'e.g. Book your stay' }, { name: 'banner_media_ids', label: 'Banner images', type: 'medias' } ] },
  { key: 'home.intro', label: 'Homepage introduction', group: 'Homepage', fields: [
    { name: 'title', label: 'Title', type: 'text' }, { name: 'body', label: 'Text', type: 'textarea' }, { name: 'media_id', label: 'Image', type: 'media' } ] },
  { key: 'about', label: 'About the hotel', group: 'Pages', fields: [
    { name: 'title', label: 'Title', type: 'text' }, { name: 'body', label: 'Story / description', type: 'textarea' }, { name: 'media_id', label: 'Image', type: 'media' },
    { name: 'highlights', label: 'Highlights', type: 'list', fields: [{ name: 'title', label: 'Title', type: 'text' }, { name: 'text', label: 'Text', type: 'textarea' }] } ] },
  { key: 'restaurant', label: 'Restaurant & dining', group: 'Pages', fields: [
    { name: 'title', label: 'Title', type: 'text' }, { name: 'intro', label: 'Introduction', type: 'textarea' }, { name: 'opening_hours', label: 'Opening hours', type: 'textarea' },
    { name: 'menu_highlights', label: 'Menu highlights', type: 'list', fields: [{ name: 'name', label: 'Dish', type: 'text' }, { name: 'description', label: 'Description', type: 'text' }, { name: 'price_minor', label: 'Price (GHS)', type: 'money' }] },
    { name: 'media_ids', label: 'Photos', type: 'medias' } ] },
  { key: 'events', label: 'Events & conferences', group: 'Pages', fields: [
    { name: 'title', label: 'Title', type: 'text' }, { name: 'intro', label: 'Introduction', type: 'textarea' }, { name: 'capacity_text', label: 'Capacity & halls', type: 'textarea' },
    { name: 'services', label: 'Services offered', type: 'list', fields: [{ name: 'title', label: 'Title', type: 'text' }, { name: 'text', label: 'Text', type: 'textarea' }] },
    { name: 'enquiry_text', label: 'How to enquire', type: 'textarea' }, { name: 'media_ids', label: 'Photos', type: 'medias' } ] },
  { key: 'contact', label: 'Contact page', group: 'Pages', fields: [
    { name: 'intro', label: 'Introduction', type: 'textarea' }, { name: 'opening_hours', label: 'Reception hours', type: 'text' },
    { name: 'directions', label: 'Directions / landmarks', type: 'textarea' }, { name: 'map_embed_url', label: 'Google Maps embed URL', type: 'text', hint: 'Paste the src of a Google Maps embed iframe' } ] },
  { key: 'footer', label: 'Footer', group: 'Pages', fields: [{ name: 'about', label: 'Short footer text', type: 'textarea' }, { name: 'copyright', label: 'Copyright line', type: 'text' }] },
  { key: 'policy.privacy', label: 'Privacy policy', group: 'Policies', fields: [{ name: 'title', label: 'Title', type: 'text' }, { name: 'body', label: 'Policy text', type: 'textarea' }] },
  { key: 'policy.terms', label: 'Terms & conditions', group: 'Policies', fields: [{ name: 'title', label: 'Title', type: 'text' }, { name: 'body', label: 'Policy text', type: 'textarea' }] },
  { key: 'policy.cancellation', label: 'Cancellation policy', group: 'Policies', fields: [{ name: 'title', label: 'Title', type: 'text' }, { name: 'body', label: 'Policy text', type: 'textarea' }] },
]
