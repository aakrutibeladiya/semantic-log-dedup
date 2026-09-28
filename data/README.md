# Data

Loghub-2k (corrected) logs are downloaded, not committed — they land in `data/raw/`
(gitignored). See main README §8.1 for which datasets (OpenSSH, Apache, Linux) and why.

Loghub is licensed for research and academic use with citation; cite it in the final
README before publishing results (see the citation block in the source repo below).

## Download

Source: [logpai/loghub](https://github.com/logpai/loghub) (the `master` branch's `_2k`
sets already incorporate the ICSE'22 "corrected" ground truth). Confirmed by fetching
the repo's README and file listing directly, not by URL guess.

```bash
mkdir -p data/raw/OpenSSH data/raw/Apache data/raw/Linux
BASE=https://raw.githubusercontent.com/logpai/loghub/master
for ds in OpenSSH Apache Linux; do
  for suffix in log log_structured.csv log_templates.csv; do
    curl -sL "$BASE/$ds/${ds}_2k.$suffix" -o "data/raw/$ds/${ds}_2k.$suffix"
  done
done
```

Gives, per dataset: the raw `.log`, a `.log_structured.csv` (parsed fields + `EventId`
ground truth, used by `eval/ground_truth.py`), and a `.log_templates.csv` (the distinct
`EventId -> EventTemplate` list, hand-labeled per query in `labels/*_template_labels.csv`).
