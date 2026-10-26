// Presentation label for the dedicated fixture; server ACL remains authoritative.
export const SAVED_PILOT_COMPANY = 'SYNTH-GATEWAY-MACRO-A'

export const isSavedPilotCompany = (id: string | null | undefined) =>
  [SAVED_PILOT_COMPANY, 'SYNTH-COLLECTION-METAL', 'SYNTH-COLLECTION-RETAIL'].includes(id ?? '')
