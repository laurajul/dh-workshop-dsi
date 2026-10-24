# Europeana API Key Setup

## Getting Your Free API Key

To use the Europeana API with full access (unlimited requests), you need a free API key:

### Step 1: Register for a Europeana Account
1. Visit: https://www.europeana.eu/
2. Click "Sign in" or "Register"
3. Create your account and confirm your email

### Step 2: Request an API Key
1. Log into your Europeana account
2. Go to your account section
3. Find the API key management area
4. Click "Request API key"
5. Fill in the simple form explaining your intended use
6. Submit your request

You should receive your API key immediately or within a few hours.

### Step 3: Save Your API Key
Once you have your key, save it to this file:

```
misc/api-key-europeana.txt
```

Just paste the key into the file (nothing else, just the key).

Example:
```bash
echo "your-api-key-here" > misc/api-key-europeana.txt
```

## Demo Key vs. Personal Key

The notebook includes a **demo key** (`api2demo`) that works out of the box, but it's limited to:
- **999 requests** total
- Shared with all demo users
- May be slower or rate-limited

Your personal key provides:
- **Unlimited requests**
- Better performance
- Option to request a project key for even higher limits

## Security

The `misc/api-key-europeana.txt` file should be added to `.gitignore` so your API key won't be accidentally committed to version control.

## What You Can Do With the API

The Europeana API gives you access to:
- **50+ million items** from 3,000+ European institutions
- **Images** from major museums (Rijksmuseum, Louvre, British Library, etc.)
- **Filtering** by country, institution, license, media type
- **IIIF support** for many items (high-resolution image access)
- **Metadata** in multiple European languages

## API Documentation

- **Main API Page**: https://pro.europeana.eu/page/apis
- **Search API Docs**: https://europeana.atlassian.net/wiki/spaces/EF/pages/2385739812/Search+API+Documentation
- **Record API Docs**: https://europeana.atlassian.net/wiki/spaces/EF/pages/2385674279/Record+API+Documentation
- **IIIF Documentation**: https://europeana.atlassian.net/wiki/spaces/EF/pages/1627914244

## Support

If you have questions or issues:
- **Email**: api@europeana.eu
- **Forum**: https://groups.google.com/g/europeanaapi

## Example Use Cases

With the Europeana API, you can:
- Search for artworks by specific artists across multiple museums
- Compare how different countries represent specific themes
- Download open-licensed images for research or education
- Build cross-institutional datasets for analysis
- Access high-resolution images through IIIF
- Create visualizations of European cultural heritage

## License Information

Europeana content has various licenses:
- **CC0**: Public domain, no restrictions
- **CC BY**: Attribution required
- **CC BY-SA**: Attribution + share-alike required
- **CC BY-NC**: Non-commercial use only
- And others...

Always check the `rights` field in the API response and provide proper attribution to both Europeana and the source institution.
