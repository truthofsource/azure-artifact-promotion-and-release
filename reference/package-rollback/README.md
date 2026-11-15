# Package rollback decision reference

This preserved platform-derived decision model supplements the new project's smaller local promotion model. It checks exact candidate/run identities, schema and preserved runtime-state contracts; it is not a cloud publisher.

Run its standard-library tests from this folder:

```bash
python -m unittest discover -s . -p 'test_*.py' -v
```

The container-signing walkthrough and the full source snapshot live in [the container lifecycle project](https://github.com/truthofsource/azure-container-lifecycle/tree/main/examples/signed-container-delivery). Historical fixture values describe test contracts rather than current production schema or configuration.
