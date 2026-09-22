#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single source of truth for the analysis threshold.

PASS is a pure function of IERR:  PASS = 1 if IERR <= IERR_MAX_PCT else 0.
IERR itself is stored at full precision for every simulated combination, so the
threshold can be changed WITHOUT re-running any simulation.

Provenance note
---------------
The LTspice decks carry `.meas tran PASS PARAM if(IERR<=1,1,0)`, i.e. the log's
own PASS column was computed with a 1.0 % criterion. That column is kept in the
stored data as provenance, but every decision in this pipeline (boundaries,
Rmax, verdicts, workbook PASS column) uses IERR_MAX_PCT from here. The parsers
still verify that the log's PASS agrees with `IERR <= 1.0`, as a check that IERR
was read correctly.
"""

IERR_MAX_PCT = 1.5

# The criterion the LTspice .meas directives themselves used -- only for
# validating the parse, never for decisions.
LOG_PASS_CRITERION_PCT = 1.0

ABS_TOL_PCT = 0.05          # near-threshold warning band, in % points


def passes(ierr, tol_pct=0.0):
    """True when an IERR value is within the configured budget."""
    return ierr is not None and ierr <= IERR_MAX_PCT + tol_pct


def verdict(ierr):
    return None if ierr is None else int(ierr <= IERR_MAX_PCT)


def fmt_pct(v):
    return f"{v:g}%"
