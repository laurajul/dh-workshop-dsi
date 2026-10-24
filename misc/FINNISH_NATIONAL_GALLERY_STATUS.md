# Finnish National Gallery API - Current Status

**Last Updated:** January 27, 2026

## Issue Summary

The Finnish National Gallery's image hosting infrastructure has changed, making image downloads from the older data package currently impossible.

## What's Not Working

### 1. CloudFront CDN (Old Image URLs)
- **Domain:** `d3uvo7vkyyb63c.cloudfront.net`
- **Status:** DNS resolution failure
- **Error:** `Failed to resolve 'd3uvo7vkyyb63c.cloudfront.net'`
- **Impact:** All image URLs in the data package return connection errors

### 2. API v2 Endpoint
- **URL:** `http://kokoelmat.fng.fi/api/v2support/docs/`
- **Status:** Connection refused
- **Impact:** Cannot access API documentation or query endpoints

### 3. IIIF Image Service
- **URL:** `https://prod-api.muzz.app/iiif/...`
- **Status:** DNS resolution failure
- **Impact:** IIIF manifest endpoints not accessible

## What Still Works

✅ **Metadata Download** - The complete data package with 80,000+ artwork records is available
✅ **Data Exploration** - All filtering, searching, and analysis of metadata works perfectly
✅ **Learning about APIs** - The notebook teaches API concepts that apply to any institution

## Your API Key

You have an API key stored in `misc/api-key.txt`. This key may work once the Finnish National Gallery restores their API services or provides updated endpoints.

## What You Can Do

### Option 1: Contact Finnish National Gallery
The most direct solution is to contact their API team:

- **Email:** api@fng.fi
- **Subject:** "Updated API v2 endpoints and image access"
- **Include:** Your API key and mention the DNS resolution errors

Ask about:
- Current status of the API v2
- New image URL patterns or CDN
- Updated API documentation
- Whether IIIF endpoints are available

### Option 2: Use Their Website
While you wait for API access:

1. Visit: https://www.kansallisgalleria.fi/en/search
2. Search for artworks (e.g., "Helene Schjerfbeck")
3. Download individual images manually (26,000+ available under CC0)
4. Right-click on images to save them

### Option 3: Alternative Cultural Heritage APIs
Consider using other institutions' APIs for learning:

- **Rijksmuseum** (Netherlands): https://data.rijksmuseum.nl/object-metadata/api/
- **Metropolitan Museum** (USA): https://metmuseum.github.io/
- **Harvard Art Museums**: https://harvardartmuseums.org/collections/api
- **Europeana**: https://pro.europeana.eu/page/apis

All of these have stable APIs with working image downloads.

## For Workshop Purposes

The notebook is still valuable for learning:
- How to work with JSON data structures
- Filtering and analyzing large datasets
- Understanding API concepts and HTTP requests
- Data exploration and visualization techniques

The only part that doesn't work is the actual image download (Part 9).

## Sources

Based on research conducted on January 27, 2026:
- [Finnish National Gallery API Page](https://www.kansallisgalleria.fi/en/api-sovelluskehittajille)
- [GitHub - Finnish National Gallery Data Dump](https://github.com/hugovk/finnishnationalgallery)
- [FNG Research](https://www.doria.fi/handle/10024/173667)

## Updates

Check back here or run `git pull` to see if we've found a solution or if the Finnish National Gallery has provided updated endpoints.
