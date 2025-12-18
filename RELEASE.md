# Release Process

This document describes how to create a new release of The Horse's Puzzle Minigames module for FoundryVTT.

## Prerequisites

- Update the `version` field in `module.json` to the new version number (e.g., "1.0.3")
- Commit and push all changes to the main branch
- Ensure all tests pass and the module works as expected

## Creating a Release

1. **Create a Git Tag**
   ```bash
   git tag -a v1.0.3 -m "Release version 1.0.3"
   git push origin v1.0.3
   ```

2. **Create a GitHub Release**
   - Go to https://github.com/ryanw341/The-Horses-Puzzle-Minigames/releases
   - Click "Draft a new release"
   - Select the tag you just created (e.g., v1.0.3)
   - Set the release title (e.g., "Version 1.0.3")
   - Add release notes describing changes
   - Click "Publish release"

3. **Automated Packaging**
   The GitHub Actions workflow (`.github/workflows/release.yml`) will automatically:
   - Package the module files into a properly structured zip
   - Exclude development files (.git, .github, .bak, .bat, .py, LocalDemo)
   - Upload the `module.zip` file as a release asset
   - The zip will have module files at the root level (required by FoundryVTT)

4. **Verify the Release**
   - Check that `module.zip` was uploaded to the release
   - Download and verify the zip structure (module.json should be at root)
   - Test installation in FoundryVTT using the manifest URL:
     ```
     https://raw.githubusercontent.com/ryanw341/The-Horses-Puzzle-Minigames/main/module.json
     ```

## Download URL Format

The `module.json` uses the following download URL format:
```
https://github.com/ryanw341/The-Horses-Puzzle-Minigames/releases/download/v{VERSION}/module.zip
```

Where `{VERSION}` matches the version in `module.json` (e.g., v1.0.2, v1.0.3).

## Important Notes

- **Do NOT use GitHub's auto-generated archive URLs** (e.g., `/archive/refs/tags/...`) as they create nested directory structures that FoundryVTT cannot handle
- **Always update the version in `module.json`** before creating a new release
- The workflow runs automatically on release publication - no manual intervention needed
- If the workflow fails, check the Actions tab for error details

## Troubleshooting

### Release asset not created
- Check the GitHub Actions logs in the "Actions" tab
- Ensure the workflow file has proper permissions
- Verify the tag was created correctly

### FoundryVTT installation fails
- Verify the zip structure: `module.json` must be at root, not in a subdirectory
- Check that the download URL in `module.json` matches the actual release version
- Ensure the release is published (not a draft)
