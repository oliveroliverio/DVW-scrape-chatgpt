#!/usr/bin/env node

/**
 * Script to download images from ChatGPT markdown files
 * Downloads images to z-img directory and updates markdown with local paths
 * Names images based on markdown title + timestamp for uniqueness
 */

const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Configuration
const config = {
    imageDir: path.resolve(__dirname, 'z-img'),
    fileExtensions: ['.md'],
    ignoreDirectories: ['node_modules', '.git', 'z-img']
};

// Ensure image directory exists
async function createImageDirectory() {
    console.log('Creating z-img directory...');
    try {
        await fs.mkdir(config.imageDir, { recursive: true });
        console.log('z-img directory created successfully');
    } catch (error) {
        console.error('Error creating z-img directory:', error);
        throw error;
    }
}

// Extract title from markdown content
function extractMarkdownTitle(content) {
    // Look for the first H1 heading
    const titleMatch = content.match(/^#\s+(.+)$/m);
    if (titleMatch) {
        // Clean the title for use in filename
        return titleMatch[1].trim()
            .replace(/[^a-zA-Z0-9\s-]/g, '') // Remove special chars except spaces and hyphens
            .replace(/\s+/g, '_') // Replace spaces with underscores
            .toLowerCase();
    }
    return 'chatgpt_conversation';
}

// Extract image URLs from markdown content (specifically looking for fig_ pattern)
function extractImageUrls(content) {
    // Look for markdown images with fig_ pattern: ![fig_timestamp](url)
    // This matches both simple fig_ patterns and ChatGPT URLs
    const imageRegex = /!\[fig_[^\]]*\]\(([^)]+)\)/g;
    const urls = [];
    let match;

    while ((match = imageRegex.exec(content)) !== null) {
        // Only process if it's a URL (starts with http)
        if (match[1].startsWith('http')) {
            urls.push({
                fullMatch: match[0],
                url: match[1],
                figName: match[0].match(/!\[(fig_[^\]]*)\]/)[1] // Extract the fig_timestamp part
            });
        }
    }

    return urls;
}

// Generate filename based on title and timestamp
function generateImageFilename(title, figName, url) {
    // Extract file extension from URL
    let extension = '.jpg'; // default
    try {
        const urlPath = new URL(url).pathname;
        const urlExt = path.extname(urlPath);
        if (urlExt) {
            extension = urlExt;
        } else if (url.includes('.png')) {
            extension = '.png';
        } else if (url.includes('.svg')) {
            extension = '.svg';
        } else if (url.includes('.gif')) {
            extension = '.gif';
        }
    } catch (e) {
        // If URL parsing fails, try to detect extension from URL string
        if (url.includes('.png')) extension = '.png';
        else if (url.includes('.svg')) extension = '.svg';
        else if (url.includes('.gif')) extension = '.gif';
    }

    // Create filename: title_figname.extension
    return `${title}_${figName}${extension}`;
}

// Download an image from URL
function downloadImage(url, filePath) {
    return new Promise((resolve, reject) => {
        const protocol = url.startsWith('https') ? https : http;

        const request = protocol.get(url, response => {
            if (response.statusCode === 200) {
                const file = fsSync.createWriteStream(filePath);
                response.pipe(file);

                file.on('finish', () => {
                    file.close();
                    response.destroy(); // Close the response stream
                    resolve(filePath);
                });

                file.on('error', (error) => {
                    file.close();
                    response.destroy();
                    reject(error);
                });
            } else if (response.statusCode === 301 || response.statusCode === 302) {
                response.destroy(); // Close current response
                // Handle redirects
                downloadImage(response.headers.location, filePath)
                    .then(resolve)
                    .catch(reject);
            } else {
                response.destroy(); // Close the response stream
                reject(new Error(`Failed to download image: ${response.statusCode} ${response.statusMessage}`));
            }
        });

        request.on('error', error => {
            request.destroy(); // Close the request
            reject(error);
        });

        // Set a timeout to prevent hanging
        request.setTimeout(30000, () => {
            request.destroy();
            reject(new Error('Request timeout'));
        });
    });
}

// Process a single markdown file
async function processMarkdownFile(filePath) {
    console.log(`Processing ${filePath}...`);

    try {
        // Read the file content
        const content = await fs.readFile(filePath, 'utf8');

        // Extract title
        const title = extractMarkdownTitle(content);
        console.log(`Extracted title: ${title}`);

        // Extract image URLs
        const imageUrls = extractImageUrls(content);

        if (imageUrls.length === 0) {
            console.log(`No ChatGPT images found in ${filePath}`);
            return;
        }

        console.log(`Found ${imageUrls.length} ChatGPT images in ${filePath}`);

        // Process each image URL
        let updatedContent = content;

        for (const { fullMatch, url, figName } of imageUrls) {
            try {
                // Generate filename
                const filename = generateImageFilename(title, figName, url);

                // Full path to save the image
                const imagePath = path.join(config.imageDir, filename);

                // Relative path for markdown (z-img is at same level as markdown file)
                const relativeImagePath = `z-img/${filename}`;

                console.log(`Downloading ${url} to ${imagePath}`);

                try {
                    // Download the image
                    await downloadImage(url, imagePath);

                    // Only update the markdown content if download was successful
                    const newImageReference = fullMatch.replace(url, relativeImagePath);
                    updatedContent = updatedContent.replace(fullMatch, newImageReference);

                    console.log(`✅ Downloaded and updated reference: ${url} -> ${relativeImagePath}`);
                } catch (downloadError) {
                    console.log(`❌ Failed to download ${url}: ${downloadError.message}`);
                    console.log(`   Keeping original URL in markdown`);
                    // Don't update the markdown - keep the original URL
                }
            } catch (error) {
                console.error(`Error processing image ${url}:`, error);
                // Continue with other images even if one fails
            }
        }

        // Write the updated content back to the file
        await fs.writeFile(filePath, updatedContent, 'utf8');

        console.log(`Updated ${filePath}`);
    } catch (error) {
        console.error(`Error processing file ${filePath}:`, error);
    }
}

// Find markdown files in current directory
async function findMarkdownFiles() {
    const files = [];
    const entries = await fs.readdir(__dirname, { withFileTypes: true });

    for (const entry of entries) {
        if (entry.isFile() && entry.name.endsWith('.md')) {
            files.push(path.join(__dirname, entry.name));
        }
    }

    return files;
}

// Main function
async function main() {
    try {
        console.log('ChatGPT Image Downloader Starting...');

        // Create necessary directory
        await createImageDirectory();

        // Find markdown files in current directory
        const markdownFiles = await findMarkdownFiles();
        console.log(`Found ${markdownFiles.length} markdown files`);

        if (markdownFiles.length === 0) {
            console.log('No markdown files found in current directory');
            return;
        }

        // Process each markdown file
        for (const file of markdownFiles) {
            await processMarkdownFile(file);
        }

        console.log('All ChatGPT markdown files processed successfully');

        // Force exit to prevent hanging
        process.exit(0);
    } catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}

// Run the script if called directly
if (require.main === module) {
    main();
}

module.exports = { main, processMarkdownFile };
