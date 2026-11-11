# GetAvailabalityAppointment

Send email for notify when practicien have disponibility.
You need the url from practicien page on doctolib or Maiia, also if you wan't 


## Requirements

- Python 3.10+
- pip or Poetry

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/your-project.git
cd your-project

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

## Usage

```python
from your_package import main

result = main.run()
print(result)
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Your API key | — |
| `DEBUG` | Enable debug mode | `False` |

## Testing

```bash
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests with `pytest`
4. Submit a pull request

## Licence

MIT