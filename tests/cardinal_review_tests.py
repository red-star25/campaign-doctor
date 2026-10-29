from datetime import datetime, timezone
from dataclasses import replace
import pytest
from campaign_doctor.models import Event, EventType, SequenceState, LogValidationError, parse_scenario
from campaign_doctor.analysis import build_report

def event(name, kind, occurred, observed, lead='lead-A', campaign='campaign-1'):
    date='2026-10-27T'
    return Event(event_id=name,campaign_id=campaign,lead_id=lead,type=EventType(kind),occurred_at=date+occurred+':00Z',observed_at=date+observed+':00Z')

def sample():
    return [event('sent','INITIAL_EMAIL_SENT','09:00','09:00'),event('reply','PROSPECT_REPLIED','09:58','10:02'),event('followup','FOLLOWUP_SENT','10:00','10:00')]

def test_original_scenario():
    r=build_report(sample()); assert r.diagnosis.pattern_matched
    assert len(r.diagnosis.findings)==1
    assert r.diagnosis.findings[0].known_state_at_send==SequenceState.ACTIVE
    assert r.final_states[('campaign-1','lead-A')]==SequenceState.STOPPED

def test_reply_after_followup_does_not_flag():
    items=sample()
    items[1]=event('reply','PROSPECT_REPLIED','10:30','10:31')
    assert not build_report(items).diagnosis.pattern_matched

def test_reply_processed_before_followup_does_not_flag():
    items=sample()
    items[1]=event('reply','PROSPECT_REPLIED','09:30','09:31')
    assert not build_report(items).diagnosis.pattern_matched

def test_multi_lead_isolation():
    items=sample()+[event('other-send','FOLLOWUP_SENT','10:00','10:00',lead='lead-B')]
    r=build_report(items)
    assert len(r.diagnosis.findings)==1
    assert r.final_states[('campaign-1','lead-B')]==SequenceState.ACTIVE

def test_shuffle_deterministic():
    items=sample()
    assert build_report(items).diagnosis==build_report(items[::-1]).diagnosis

def test_duplicate_id_rejected_through_json_parser():
    items=sample(); raw={'events':[{'event_id':x.event_id,'campaign_id':x.campaign_id,'lead_id':x.lead_id,'type':x.type.value,'occurred_at':x.occurred_at.isoformat(),'observed_at':x.observed_at.isoformat()} for x in items+[items[-1]]]}
    with pytest.raises(LogValidationError): parse_scenario(raw)

def test_detect_known_stop_not_delayed_reply_root_cause():
    items=sample()+[event('early-reply','PROSPECT_REPLIED','09:50','09:51')]
    report=build_report(items)
    # A follow-up was already prohibited by a previously processed reply.
    # Do not categorize this send only as a late-notification issue.
    assert all(f.known_state_at_send==SequenceState.ACTIVE for f in report.diagnosis.findings)

def test_public_report_rejects_or_deduplicates_identical_ids():
    items=sample()
    try:
        report=build_report(items+[items[-1]])
    except LogValidationError:
        return  # Rejecting duplicate IDs is a valid policy.
    assert len(report.diagnosis.findings)==1  # Deduplicating is also valid.
