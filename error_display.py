# Improve error summaries to include tooltips from spec descriptions
def display_validation_errors(errors, spec):
    # Get spec fields
    spec_fields = spec.get('fields', {})
    # Display errors with tooltips
    for error in errors:
        field = error.get('field', '')
        tooltip = spec_fields.get(field, {}).get('description', '')
        st.error(f"{error.get('message', '')} - {tooltip}") 