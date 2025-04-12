# Personal Website

This is my personal website built with [Zola](https://www.getzola.org/), a modern static site generator.

## Development

1. Install Zola:
   ```bash
   # macOS
   brew install zola
   ```

2. Run the development server:
   ```bash
   zola serve
   ```

3. Open http://127.0.0.1:1111 in your browser

## Deployment

This site is deployed on Cloudflare Pages. The deployment is automatic when changes are pushed to the main branch.

### Local Build

To build the site locally:
```bash
zola build
```

The built site will be in the `public` directory.

## Project Structure

- `content/`: Contains all the content (pages, blog posts)
- `static/`: Static files (images, CSS, etc.)
- `templates/`: Tera templates
- `themes/`: Theme files
- `config.toml`: Site configuration 