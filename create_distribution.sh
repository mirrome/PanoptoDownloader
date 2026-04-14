#!/bin/bash
# Create a distribution package for sharing

echo "Creating Panopto Downloader distribution package..."

# Create distribution directory
DIST_DIR="panopto-downloader-package"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Copy essential files
echo "Copying files..."
cp -r src "$DIST_DIR/"
cp -r tests "$DIST_DIR/"
cp README.md "$DIST_DIR/"
cp SIMPLE_SETUP.md "$DIST_DIR/"
cp WINDOWS_SETUP.md "$DIST_DIR/"
cp SHARING_GUIDE.md "$DIST_DIR/"
cp setup.sh "$DIST_DIR/"
cp setup.bat "$DIST_DIR/"
cp setup.ps1 "$DIST_DIR/"
cp requirements.txt "$DIST_DIR/"
cp requirements-dev.txt "$DIST_DIR/"
cp pyproject.toml "$DIST_DIR/"
cp LICENSE "$DIST_DIR/"
cp config.example.yaml "$DIST_DIR/"

# Make setup scripts executable
chmod +x "$DIST_DIR/setup.sh"

# Copy example YAML files (as references)
echo "Copying example configs..."
cp deploying_ai.yaml "$DIST_DIR/example_deploying_ai.yaml"
cp disciplined_entrepreneurship.yaml "$DIST_DIR/example_disciplined_entrepreneurship.yaml"

# Create a quick start file
cat > "$DIST_DIR/QUICK_START.txt" << 'EOF'
PANOPTO DOWNLOADER - QUICK START
=================================

🚀 SUPER SIMPLE SETUP (2 steps):

1. RUN THE SETUP SCRIPT:
   cd panopto-downloader-package
   ./setup.sh
   
   (If you get "permission denied", run: chmod +x setup.sh)

2. THAT'S IT! Now create your config:
   source venv/bin/activate
   panopto-downloader init -o my_course.yaml
   
3. EDIT my_course.yaml to add your lecture URLs

4. DOWNLOAD:
   - Log into Panopto in Chrome
   - Close Chrome (Cmd+Q)
   - panopto-downloader -c my_course.yaml download

FOR NEW TERMINAL SESSIONS:
   cd panopto-downloader-package
   source venv/bin/activate
   panopto-downloader -c my_course.yaml download

📖 See SIMPLE_SETUP.md for detailed instructions!
📚 See SHARING_GUIDE.md for advanced features!
EOF

# Create ZIP
echo "Creating ZIP archive..."
zip -r panopto-downloader-package.zip "$DIST_DIR" > /dev/null

echo ""
echo "✅ Distribution package created!"
echo ""
echo "📦 Package location: $DIST_DIR/"
echo "📦 ZIP file: panopto-downloader-package.zip"
echo ""
echo "To share:"
echo "  - Upload panopto-downloader-package.zip to Google Drive/Dropbox"
echo "  - Or create a GitHub repo and push the contents of $DIST_DIR/"
echo ""
echo "The recipient should:"
echo "  1. Extract the ZIP"
echo "  2. Follow instructions in QUICK_START.txt or SHARING_GUIDE.md"
