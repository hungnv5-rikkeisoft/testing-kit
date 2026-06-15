# Screen: Basic Information Input

Test level: IT

## Components
- Usage: two buttons "Residential" / "Industrial" (single-select).
- Property Region: two dropdowns "Prefecture" (47 items) and "Municipality"
  (depends on Prefecture).
- Submit button.

## Business rules
- Selecting a Prefecture loads its Municipalities and clears prior Municipality.
- Submitting with required fields empty shows a validation error.
- Input must be safe against HTML/script injection.
