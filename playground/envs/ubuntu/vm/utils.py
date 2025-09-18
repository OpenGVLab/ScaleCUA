from urllib.parse import urlparse, urlunparse

def compare_urls(url1, url2):
    if url1 is None or url2 is None:
        return url1 == url2

    def normalize_url(url):
        # Parse the URL
        parsed_url = urlparse(url)

        # If no scheme is present, assume 'http'
        scheme = parsed_url.scheme if parsed_url.scheme else 'http'

        # Lowercase the scheme and netloc, remove 'www.', and handle trailing slash
        normalized_netloc = parsed_url.netloc.lower().replace("www.", "")
        normalized_path = parsed_url.path if parsed_url.path != '/' else ''

        # Reassemble the URL with normalized components
        normalized_parsed_url = parsed_url._replace(scheme=scheme.lower(), netloc=normalized_netloc,
                                                    path=normalized_path)
        normalized_url = urlunparse(normalized_parsed_url)

        return normalized_url

    # Normalize both URLs for comparison
    norm_url1 = normalize_url(url1)
    norm_url2 = normalize_url(url2)

    # Compare the normalized URLs
    return norm_url1 == norm_url2