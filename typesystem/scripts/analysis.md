# Type System Analysis

## Generate type system representation via LLM

Status: done

## Understand difficulties in the specification regarding the type system

Status: WIP

LLM used: kit.qwen3.5-397b-A17b

Findings:

- It is confusing that e.g. AttributeDef is not a attribute definition (despite the name), but a profile. Probably a hard case for an LLM, but also potentially difficult for human readers.
- The LLM was not sure how to represent "optional values", meaning values which have a cardinality that includes 0 occurences and put them into the profile, which implies they have to occur. This points out that the type system cannot represent the whole specification. There are certain things people have to know, especially when it comes to describing the value syntax (e.g. what is the attribute so I can use a regular expression instead of a primitive). Especially for the core profiles, we need to revise which attributes are contained (and therefore mandatory).

## Implement a validator, validate it using tests.

Note: This is done with excessive help of the LLM model stated above (especially at the beginning) and will be human-reviewed in the end, as well as in the process.

Goal:

- [x] A validation that works for any FDO, no matter if it is a type or not.
- [x] Attribute validation: Check if the values fit to their attribute definitions.
- [x] Profile validation: Check if all mandatory attributes are present.
- [ ] Specification validation: Check things the type system does not represent. Not sure what comes in here.
- [?] Dependency validation: This is (currently) implicit to all the other validations. It means that all encountered and used FDOs are also checked.

Status: Normally, next would be Phase 6. See [Implementation plan](docs/implementation_plan.md) and phase reports in the same folder. But we are now in a state where we should check the tests, especially for the validators. We should correct them to the expected behaviour and correct then the code accordingly, before we proceed.

## Use the validation implementation (especially attribute validation) to verify the type system is complete.

Goal: So far, no missing types seem to be found. But as soon as the validator is fully working, we can see if attribute validation succeeds on all FDOs. If so, we are complete.
