# Real Footage Archive

This directory contains publicly accessible real video footage used for
Phase 5 validation of the Time Compression Engine.

## License

All footage in `videos/` is from archive.org. Each clip has a corresponding
`metadata/` YAML file documenting its source, license, and characteristics.

Videos are NOT committed to git (listed in .gitignore).
Metadata files ARE committed.

## Clips

| ID | File | Source | License | People |
|---|---|---|---|---|
| archive_001 | WhenYouA1948_512kb.mp4 | archive.org/details/WhenYouA1948 | Public Domain | Yes — pedestrians on Oakland streets |
| archive_002 | 53224_Night_Driving.mp4 | archive.org/details/53224NightDriving | Public Domain | Yes — pedestrians at night, LA |

## Usage

These clips test:
- archive_001: Daytime pedestrian detection (outdoor, moving people)
- archive_002: Night/low-light detection (LA streets at night)

## Notes

- Do NOT add copyrighted footage to this directory.
- Do NOT commit raw video files to git.
- Always document the source URL and license before using any footage.
