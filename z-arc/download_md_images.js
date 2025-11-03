#!/usr/bin/env node

/**
 * Script to download all images referenced in markdown files and update links to use local paths
 * This ensures images persist even if external URLs break
 */

const fs = require('fs').promises;
const fsSync = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { promisify } = require('util');
const { exec } = require('child_process');
const execAsync = promisify(exec);

// Configuration
const config = {
    rootDir: path.resolve(__dirname, '..'),
    imageDir: path.resolve(__dirname, '../images-md'),
    subdirectories: {
        auth: 'auth',
        ui: 'ui',
        icons: 'icons',
        diagrams: 'diagrams',
        avatars: 'avatars',
        misc: 'misc'
    },
    fileExtensions: ['.md'],
    ignoreDirectories: ['node_modules', '.git']
};

// Ensure image directories exist
async function createDirectories() {
    console.log('Creating image directories...');

    try {
        await fs.mkdir(config.imageDir, { recursive: true });

        for (const dir of Object.values(config.subdirectories)) {
            await fs.mkdir(path.join(config.imageDir, dir), { recursive: true });
        }

        console.log('Image directories created successfully');
    } catch (error) {
        console.error('Error creating directories:', error);
        throw error;
    }
}

// Find all markdown files in the repository
async function findMarkdownFiles(dir, fileList = []) {
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
            if (!config.ignoreDirectories.includes(entry.name)) {
                await findMarkdownFiles(fullPath, fileList);
            }
        } else if (config.fileExtensions.some(ext => entry.name.endsWith(ext))) {
            fileList.push(fullPath);
        }
    }

    return fileList;
}

// Extract image URLs from markdown content
function extractImageUrls(content) {
    const imageRegex = /!\[.*?\]\((https?:\/\/[^)]+)\)/g;
    const emptyImageRegex = /\[\]\((https?:\/\/[^)]+)\)/g;
    const urls = [];
    let match;

    while ((match = imageRegex.exec(content)) !== null) {
        urls.push({
            fullMatch: match[0],
            url: match[1]
        });
    }

    while ((match = emptyImageRegex.exec(content)) !== null) {
        urls.push({
            fullMatch: match[0],
            url: match[1]
        });
    }

    return urls;
}

// Determine appropriate subdirectory for an image
function determineImageSubdirectory(url) {
    const urlLower = url.toLowerCase();

    if (urlLower.includes('avatar') || urlLower.includes('profile') || urlLower.includes('photo') || urlLower.includes('thumb')) {
        return config.subdirectories.avatars;
    } else if (urlLower.includes('auth') || urlLower.includes('token') || urlLower.includes('login') || urlLower.includes('jwt')) {
        return config.subdirectories.auth;
    } else if (urlLower.includes('icon') || urlLower.includes('svg') || urlLower.includes('logo')) {
        return config.subdirectories.icons;
    } else if (urlLower.includes('diagram') || urlLower.includes('flow') || urlLower.includes('architecture')) {
        return config.subdirectories.diagrams;
    } else if (urlLower.includes('screenshot') || urlLower.includes('screen') || urlLower.includes('ui') || urlLower.includes('page')) {
        return config.subdirectories.ui;
    } else {
        return config.subdirectories.misc;
    }
}

// Generate a safe filename from URL
function generateSafeFilename(url) {
    // Extract the original filename from the URL
    let filename = path.basename(new URL(url).pathname);

    // If the filename has a query string, remove it
    if (filename.includes('?')) {
        filename = filename.split('?')[0];
    }

    // If filename doesn't have an extension, try to determine from URL or default to .jpg
    if (!path.extname(filename)) {
        if (url.includes('.jpg') || url.includes('.jpeg')) {
            filename += '.jpg';
        } else if (url.includes('.png')) {
            filename += '.png';
        } else if (url.includes('.svg')) {
            filename += '.svg';
        } else if (url.includes('.gif')) {
            filename += '.gif';
        } else {
            filename += '.jpg'; // Default extension
        }
    }

    // Replace any remaining special characters
    filename = filename.replace(/[^a-zA-Z0-9._-]/g, '_');

    // Add a timestamp to ensure uniqueness
    const timestamp = Date.now();
    const filenameWithoutExt = path.basename(filename, path.extname(filename));
    const ext = path.extname(filename);

    return `${filenameWithoutExt}_${timestamp}${ext}`;
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
                    resolve(filePath);
                });
            } else if (response.statusCode === 301 || response.statusCode === 302) {
                // Handle redirects
                downloadImage(response.headers.location, filePath)
                    .then(resolve)
                    .catch(reject);
            } else {
                reject(new Error(`Failed to download image: ${response.statusCode} ${response.statusMessage}`));
            }
        });

        request.on('error', error => {
            reject(error);
        });
    });
}

// Process a markdown file
async function processMarkdownFile(filePath) {
    console.log(`Processing ${filePath}...`);

    try {
        // Read the file content
        const content = await fs.readFile(filePath, 'utf8');

        // Extract image URLs
        const imageUrls = extractImageUrls(content);

        if (imageUrls.length === 0) {
            console.log(`No image URLs found in ${filePath}`);
            return;
        }

        console.log(`Found ${imageUrls.length} image URLs in ${filePath}`);

        // Process each image URL
        let updatedContent = content;

        for (const { fullMatch, url } of imageUrls) {
            try {
                // Determine subdirectory
                const subdir = determineImageSubdirectory(url);

                // Generate safe filename
                const filename = generateSafeFilename(url);

                // Full path to save the image
                const imagePath = path.join(config.imageDir, subdir, filename);

                // Relative path for markdown
                const relativeImagePath = path.relative(
                    path.dirname(filePath),
                    imagePath
                ).replace(/\\/g, '/'); // Ensure forward slashes for markdown

                console.log(`Downloading ${url} to ${imagePath}`);

                // Download the image
                await downloadImage(url, imagePath);

                // Update the markdown content
                const newImageReference = fullMatch.replace(url, relativeImagePath);
                updatedContent = updatedContent.replace(fullMatch, newImageReference);

                console.log(`Updated reference: ${url} -> ${relativeImagePath}`);
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

// Main function
async function main() {
    try {
        // Create necessary directories
        await createDirectories();

        // Find all markdown files
        const markdownFiles = await findMarkdownFiles(config.rootDir);
        console.log(`Found ${markdownFiles.length} markdown files`);

        // Process each markdown file
        for (const file of markdownFiles) {
            await processMarkdownFile(file);
        }

        console.log('All markdown files processed successfully');
    } catch (error) {
        console.error('Error:', error);
        process.exit(1);
    }
}

// Run the script
main();