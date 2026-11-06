## What

<!-- One or two sentences: what changes and why. Link the plan task or issue. -->

## How it was tested

- [ ] `bench --site <site> run-tests --app onebook_fenestration`
- [ ] Engine: `../../env/bin/python -m unittest discover -s onebook_fenestration/engine/tests -t .`
- [ ] Frontend: `cd frontend && yarn test`
- [ ] Checked in the browser (desktop and 390 px) if the UI changed

## Checklist

- [ ] Golden designs W01 / W02 / 123 still match EvA
- [ ] No series-specific numbers hardcoded in the engine
- [ ] `doc/decisions.md` updated if a decision was made or changed
- [ ] No customer data (PDFs, DXFs, videos, names, phone numbers) committed
