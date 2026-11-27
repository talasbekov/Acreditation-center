// Older versions of the attendee form saved one draft per browser profile.
try {
  window.localStorage.removeItem('attendee_draft_v1')
} catch {
  // Storage can be disabled on a shared workstation.
}
