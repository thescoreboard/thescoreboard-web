// Setup checklist — drives the "Setup Progress" accordion on the tournament
// Info page. Each item counts as one of the N required details; Basic Info
// and Format & Play are worth several items each so that an already-configured
// event (name/format/participant type set at creation) starts mostly done.
function prizeRulesContactItems(t) {
  const info = t.tournament_info || {};
  const contact = info.contact || {};
  return [
    { key: "prize_pool",     section: "prize",   label: "Prize Pool",            done: (info.prize_pool || []).length > 0 },
    { key: "rules",          section: "rules",    label: "Rules & Regulations",   done: !!(info.rules && info.rules.trim()) },
    { key: "reg_deadline",   section: "contact",  label: "Registration Deadline", done: !!contact.reg_deadline },
    { key: "contact_person", section: "contact",  label: "Contact Person",        done: (contact.persons || []).some(p => p.name && p.phone) },
  ];
}

function basicInfoItems(t) {
  return [
    { key: "venue",      section: "basic", label: "Venue",       done: !!t.venue },
    { key: "city_state", section: "basic", label: "City & State", done: !!(t.city && t.state) },
    { key: "start_date", section: "basic", label: "Start Date",   done: !!t.start_date },
    { key: "end_date",   section: "basic", label: "End Date",     done: !!t.end_date },
  ];
}

// Single-sport / per-event workspace — Format & Play reflects this event's
// own format + participant type (already set at creation, so this section
// is typically complete immediately).
export function getEventSetupChecklist(t, event) {
  return [
    ...basicInfoItems(t),
    { key: "format",      section: "format", label: "Tournament Format", done: !!event?.format },
    { key: "participant", section: "format", label: "Participant Type",  done: !!event?.participant_type },
    ...prizeRulesContactItems(t),
  ];
}

// Multi-sport landing page — there's no single event, so Format & Play
// reflects whether every sport in the tournament has been configured.
export function getTournamentSetupChecklist(t, allSportsConfigured) {
  return [
    ...basicInfoItems(t),
    { key: "sports_configured_a", section: "format", label: "Sports Configured", done: !!allSportsConfigured },
    { key: "sports_configured_b", section: "format", label: "Sports Configured", done: !!allSportsConfigured },
    ...prizeRulesContactItems(t),
  ];
}

export function summarizeChecklist(items) {
  const doneCount  = items.filter(i => i.done).length;
  const totalCount = items.length;
  return {
    doneCount,
    totalCount,
    percent:  totalCount ? Math.round((doneCount / totalCount) * 100) : 100,
    complete: doneCount === totalCount,
  };
}

export function isSectionComplete(items, section) {
  const secItems = items.filter(i => i.section === section);
  return secItems.length > 0 && secItems.every(i => i.done);
}
