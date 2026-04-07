# AIReader

AI-powered PDF reader with intelligent document processing and analysis capabilities.

## Description

AIReader is a Python application that combines PDF file reading with artificial intelligence functionality. The application provides an intuitive interface for working with PDF documents while leveraging AI models for enhanced document understanding and processing.

## Features

- PDF file reading and display
- AI-powered document analysis
- Intelligent page conversion and processing
- User-friendly graphical interface
- GPU acceleration support for fast page conversion

## Requirements

- Python 3.14 or higher
- GPU support (optional, recommended for optimal performance during page conversion)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AdeptOfStroggus/AIReader.git
cd AIReader
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
```

Edit the `.env` file and add your API keys and configuration parameters as needed.

## Usage

To start the application:
```bash
python ui.py
```

## Performance Recommendations

For optimal performance when converting PDF pages, it is strongly recommended to use a GPU. GPU acceleration significantly speeds up page processing and rendering compared to CPU-only mode.

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the LICENSE file for details.

## Contributing

Contributions are welcome. Please feel free to submit issues and pull requests.
