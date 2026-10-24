# API Key Configuration

## Finnish National Gallery

**Note:** The Finnish National Gallery's open data does **NOT require an API key**. The images are publicly accessible under a CC0 license.

## If You Need an API Key

Some other cultural heritage APIs may require authentication. If you need to use an API key:

1. Create a file called `api-key.txt` in this directory
2. Paste your API key into that file (just the key, nothing else)
3. The notebook will automatically load it

Example:
```bash
echo "your-api-key-here" > misc/api-key.txt
```

## Security

The `misc/api-key.txt` file is automatically excluded from git via `.gitignore`, so your API key won't be accidentally committed to version control.
