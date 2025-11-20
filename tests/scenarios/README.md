# Test Scenarios

This directory contains natural language test scenarios for automated gameplay testing.

## How It Works

1. Each `.md` file describes a test scenario in plain English
2. Claude reads the scenario and executes it using pexpect MCP
3. Claude controls the game, makes decisions, and verifies outcomes
4. Any bugs, crashes, or unexpected behavior are reported

## Scenario Template

```markdown
# Test Scenario: [Name]

## Objective
[What this test verifies]

## Setup Steps
[How to get the game into the starting state]

## Test Actions
[What actions to perform during the test]

## Expected Outcomes
[What should happen - use ✓ for success criteria]

## Failure Conditions
[What constitutes a test failure - use ✗ for failure criteria]

## Notes
[Additional context, edge cases, or extensions]
```

## Running Scenarios

### Manual Execution (Current)
Ask Claude to execute a scenario:
```
"Execute the scenario in tests/scenarios/basic_combat.md using pexpect MCP"
```

### Automated Execution (Future)
```bash
pytest tests/test_automated_scenarios.py
```

## Writing Good Scenarios

- **Be specific** about setup steps
- **Define clear** success/failure criteria
- **Keep scenarios focused** on one aspect of gameplay
- **Include edge cases** that might reveal bugs
- **Document assumptions** about game state

## Scenario Categories

- **Smoke Tests** - Basic functionality, quick validation
- **Combat Tests** - Fighting mechanics, damage, death
- **Exploration Tests** - Navigation, room transitions, searching
- **Character Tests** - Leveling, abilities, inventory
- **Edge Cases** - Boundary conditions, error handling
