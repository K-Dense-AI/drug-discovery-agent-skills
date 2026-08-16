# Error Handling and Troubleshooting

Common errors — invalid SMILES, missing API key, insufficient credits, failed workflows,
and polling a workflow that is not yet done — with fixes, plus debugging tips.

## Error handling and troubleshooting

### Common errors and solutions

```python
import rowan

# Error 1: Invalid SMILES
try:
    wf = rowan.submit_descriptors_workflow("CCCC(CC", name="bad smiles")  # Invalid
except rowan.ValidationError as e:
    print(f"Invalid SMILES: {e}")
    # Solution: Use RDKit to validate before submission
    from rdkit import Chem
    smi = Chem.MolToSmiles(Chem.MolFromSmiles(smi))

# Error 2: API key not set
try:
    wf = rowan.submit_descriptors_workflow("CCO")
except rowan.AuthenticationError:
    print("API key not found. Set ROWAN_API_KEY env var or call rowan.api_key = '...'")

# Error 3: Insufficient credits
try:
    wf = rowan.submit_protein_cofolding_workflow(...)
except rowan.InsufficientCreditsError as e:
    print(f"Not enough credits: {e}. Purchase more or reduce job size.")

# Error 4: Workflow failed (bad molecule, etc.)
try:
    wf = rowan.submit_docking_workflow(...)
    result = wf.result()
except rowan.WorkflowError as e:
    print(f"Workflow failed: {e}")
    # Check wf.status for details
    print(f"Status: {wf.status}")

# Error 5: Workflow not yet done — poll manually
result = wf.result(wait=True, poll_interval=5)  # waits and polls every 5s
# Or check status without blocking:
if not wf.done():
    print("Workflow still running. Call wf.result() again later.")
```

### Debugging tips

- **Check workflow status**: `wf.status`, check `wf.done()`, or call `wf.get_status()`
- **Inspect raw result**: `result.data` instead of convenience properties
- **Re-run failed workflow**: Save UUIDs and retry with `rowan.retrieve_workflow(uuid)`
- **Validate molecules beforehand**: Use RDKit or Chemaxon before batch submission
