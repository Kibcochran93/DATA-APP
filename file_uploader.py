# Refactor encoding logic into helpers
def detect_encoding(file):
    # Detect file encoding
    import chardet
    rawdata = file.read()
    result = chardet.detect(rawdata)
    file.seek(0)
    return result['encoding']

# Show normalized header preview earlier
def show_header_preview(df):
    # Show normalized header preview
    st.write('Normalized Headers:')
    st.write(df.columns)

# Improve error message readability
def handle_upload_error(error):
    # Improve error message readability
    st.error(f'Error uploading file: {str(error)}') 