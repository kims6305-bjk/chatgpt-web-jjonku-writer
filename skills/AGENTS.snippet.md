<!-- Append to the target repository's AGENTS.md so the web agent knows its contract. -->

When the web ChatGPT git-writer connector is selected, web ChatGPT is the primary autonomous coding
agent for this repository. It must translate the request into a complete implementation without
waiting for another orchestrator: read this file, reproduce the finding, change every required
source file and its directly related tests, inspect the full diff, run the applicable checks, fix
failures, commit and push only to `chatgpt/*`, open or update a pull request, and squash-merge it
once required checks pass. It must not impose arbitrary file-count or scope limits.

It must never push directly to the base branch, force-push, delete branches, expose secrets, weaken
or delete tests, or modify protected repository, workflow, credential, or writer files.
