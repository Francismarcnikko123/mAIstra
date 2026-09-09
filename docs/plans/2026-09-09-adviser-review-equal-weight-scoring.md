# Task: Adviser Review of Equal-Weight Test Scoring

**Status:** Pending adviser review

## Prototype to review

- Each passed test case earns `1`; each failed case earns `0`.
- Score percentage is `(passed / total) * 100`.
- All test cases are equally weighted.
- The UI shows both the passed fraction and percentage.
- Logic analysis is feedback only and does not change the score.
- This partial implementation displays the score but does not persist it.

## Questions for the adviser

- [ ] Is equal weighting (`1` point per test case) correct?
- [ ] Should the test-case percentage be the entire final score for the question?
- [ ] Is rounding repeating percentages to two decimal places acceptable?
- [ ] Should compilation failure simply make every affected test case worth `0`?
- [ ] Should the calculated score be saved in Supabase?
- [ ] Should teachers be allowed to override the automatic score?
- [ ] Should Logic Analysis remain diagnostic only?

## Follow-up after approval

- [ ] Record the adviser-approved formula in the thesis rubric.
- [ ] Adjust the prototype if the adviser changes the formula.
- [ ] Add score persistence only if approved.
- [ ] Add any approved manual-review component as a separate task.
