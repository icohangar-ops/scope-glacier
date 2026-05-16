# CHP State Machine — scope-glacier

## Protocol: Consensus Hardening Protocol (CHP) v1.0
## Domain: Mining / Supply Chain
## Applied: 2026-05-16

### States
- EXPLORING: Initial decision exploration with foundation disclosure
- PROVISIONAL: Foundation score ≥75, devil's advocate complete
- PROVISIONAL_LOCK: Ready for third-party validation
- LOCKED: Third-party CONFIRM received, decision committed
- CONVERGED: Cross-agent agreement achieved
- UNRESOLVED: Forced at round 5 if no convergence
- REQUIRES_HUMAN_VERIFICATION: CFO accuracy guard tripped
- REFRAME_REQUIRED: Foundation score <75
- HALT: R0 gate fatal or context parity significant

### Phase Progression
FOUNDATION (Phase 0) → SPEC (Phase 1) → IMPLEMENTATION (Phase 2)
Phase transitions occur at round boundaries: FOUNDATION→SPEC at round 1, SPEC→IMPLEMENTATION at round 3.

### State Transitions
- EXPLORING → PROVISIONAL: Foundation score ≥ 75, ESG and geopolitical risks assessed
- EXPLORING → REFRAME_REQUIRED: Foundation score < 75
- PROVISIONAL → PROVISIONAL_LOCK: Devil's advocate complete, supply chain resilience validated
- PROVISIONAL_LOCK → LOCKED: Third-party CONFIRM received with supply chain validation
- PROVISIONAL_LOCK → EXPLORING: Third-party REJECT with supply chain correction criteria
- LOCKED → CONVERGED: Cross-agent consensus achieved
- Any → HALT: Critical supply chain disruption risk identified
- Any → UNRESOLVED: Forced at round 5 if no supply chain consensus

### R0 Gate (Session Entry)
All four checks must PASS:
- Solvable: The decision can be resolved within the domain's constraints
- Scoped: Clear scope boundaries defined in dossier
- Valid: Current state and goal state are specified
- Worth_it: Stakes justify the governance overhead

### Foundation Score Thresholds
- General: ≥70 PASS, <70 REFRAME
- Finance/CFO: ≥100 (CFOAccuracyPolicy), <100 REQUIRES_HUMAN_VERIFICATION
- Blockchain/DeFi: ≥85 (elevated due to immutable tx risk)

### Adversary Schedule
- Phase 0, Round 0: Mandatory devil's advocate from FoundationDisclosure + FoundationAttack
- Phase 2, Round 3: Implementation drift check devil's advocate
- Council Spawn: high_stakes=True AND confidence <85 → 3-model cross-review

### Third-Party Validation
- PROVISIONAL_LOCK → CONFIRM → LOCKED
- PROVISIONAL_LOCK → REJECT → EXPLORING (with flip_criteria)
