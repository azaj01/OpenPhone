# iOS Agent

An intelligent iOS automation framework that enables GUI agents to interact with iOS applications through WebDriverAgent (WDA), capture screenshots during task execution, and perform advanced analysis using RAG (Retrieval-Augmented Generation) systems.

## Overview

The iOS Agent provides a complete pipeline for:
1. **Automated GUI Operations**: Control iOS apps through vision-language models to perform complex tasks
2. **Screenshot Capture**: Automatically capture and save screenshots during task execution
3. **Content Analysis**: Analyze captured screenshots using RAG systems to generate comprehensive reports

## Architecture

```
ios_agent/
├── connection.py          # WebDriverAgent connection management
├── controller.py          # iOS device controller
├── executor.py            # Action execution engine
├── task.py                # Task management and orchestration
├── recorder.py            # Task recording and logging
├── application/           # Application-specific pipelines
│   └── mail/             # Mail app automation + RAG analysis
└── run_ios_agent.py      # General-purpose iOS agent runner
```

## Prerequisites

### 1. WebDriverAgent (WDA)

WebDriverAgent must be running on your iOS device or simulator.

- **Default URL**: `http://localhost:8100`
- **Remote Device**: Use `http://<device-ip>:8100` for devices on the same network
- **USB Forwarding**: Use `iproxy 8100 8100` for USB-connected devices

For detailed iOS environment setup instructions, refer to the [Open-AutoGLM iOS Setup Guide](https://github.com/zai-org/Open-AutoGLM/blob/main/docs/ios_setup/ios_setup.md).

For general WebDriverAgent documentation, see the [WebDriverAgent repository](https://github.com/appium/WebDriverAgent).

### 2. Environment Variables

Set the following environment variables for the vision-language models:

**For GUI Agent (Mail automation):**
```bash
# Required: API base URL for the LLM service (GUI agent uses port 8002)
export API_BASE='http://localhost:8002/v1'

# Required: Model name for GUI agent
export MODEL_NAME='Qwen/Qwen2.5-3B-Instruct'

# Optional: API key (not required for local agents, defaults to "EMPTY")
export API_KEY='EMPTY'

# Optional: Agent type (defaults to "OpenAIAgent")
export AGENT_TYPE='OpenAIAgent'  # or 'QwenVLAgent'

# Optional: WDA URL (defaults to http://localhost:8100)
export WDA_URL='http://localhost:8100'
```

**For RAG Analysis (Screenshot analysis):**
```bash
# Required: API base URL for the LLM service (RAG system uses port 8003)
export API_BASE='http://localhost:8003/v1'

# Required: Model name for RAG analysis
export MODEL_NAME='Qwen3-VL-4B-Instruct'

# Optional: API key (not required for local agents, defaults to "EMPTY")
export API_KEY='EMPTY'

# Optional: Agent type (defaults to "OpenAIAgent")
export AGENT_TYPE='OpenAIAgent'  # or 'QwenVLAgent'
```

**Note**: The GUI agent and RAG system use different default ports (8002 and 8003 respectively). If you're using the combined `run_mail_and_rag.sh` script, you may need to set `API_BASE` twice - once before running the script for the GUI agent, and the RAG system will use its own default (port 8003) unless you set it explicitly.

### 3. Python Dependencies

Install required Python packages:

```bash
pip install -r requirements.txt
```

## Quick Start: Mail Application Pipeline

The Mail application pipeline demonstrates the complete workflow: automated GUI operations followed by RAG-based content analysis.

The Mail agent automatically:
1. Opens the Mail app on iOS
2. Navigates to the inbox/mail list
3. Identifies the top 5 most recent emails
4. Opens each email sequentially, views content, and returns to the list
5. Captures screenshots at each step
6. Analyzes the captured screenshots using RAG to extract email information, classify emails, and generate comprehensive reports

### Running the Complete Pipeline

Use the combined script that runs both GUI automation and RAG analysis automatically:

```bash
cd ios_agent/application/mail

# Basic usage - run GUI agent, then automatically analyze the generated screenshots
./run_mail_and_rag.sh

# With custom WDA URL
./run_mail_and_rag.sh --wda-url http://192.168.1.10:8100

# With custom parameters
./run_mail_and_rag.sh --wda-url http://192.168.1.10:8100 --max-rounds 80 --target-email-count 5
```

This script automatically:
1. Executes the Mail GUI agent to perform automated operations and capture screenshots
2. Locates the latest `ios_logs/mail_task_*/screenshots` directory created by the GUI agent
3. Runs RAG analysis on the captured screenshots to extract email information
4. Generates comprehensive analysis reports (text report and JSON data)

The RAG system analyzes screenshots to:
- Extract email information (sender, subject, content summary)
- Classify emails by type (Work/Business, Personal/Social, Newsletter/Marketing, etc.)
- Assess importance levels (1-5 scale)
- Generate structured reports

## Output Structure

### GUI Agent Output

Task logs and screenshots are saved in `Android-Lab/ios_logs/<task_name>/`:

```
ios_logs/
└── mail_task_<timestamp>_<date>/
    ├── screenshots/          # Screenshots captured during execution
    │   ├── screenshot_0.png
    │   ├── screenshot_1.png
    │   └── ...
    ├── traces/               # Execution traces (trace.jsonl)
    └── xml/                  # Page XML structures
```

### RAG Analysis Output

RAG analysis generates two files in the task directory:

```
ios_logs/
└── mail_task_<timestamp>_<date>/
    ├── mail_analysis_report.txt    # Human-readable analysis report
    └── mail_analysis_data.json     # Structured JSON data
```

**Report Contents:**
- Summary by email type
- Summary by importance level
- Detailed information for each email
- Statistics (average importance, most common sender, etc.)

## Mail Pipeline Parameters

The `run_mail_and_rag.sh` script accepts parameters that are passed to the GUI agent. The RAG analysis step uses default settings (can be configured via environment variables).

### GUI Agent Parameters (passed to run_mail_and_rag.sh)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--wda-url` | `http://localhost:8100` | WebDriverAgent URL |
| `--max-rounds` | `80` | Maximum number of interaction rounds |
| `--target-email-count` | `5` | Number of emails to open |
| `--request-interval` | `2.0` | Interval between requests (seconds) |
| `--task-dir` | `ios_logs/mail_task_xxx/` | Directory to save logs and screenshots |
| `--max-no-progress-rounds` | `15` | Allow finishing if no progress for N rounds |
| `--open-mail-timeout` | `10` | Force move on if stuck opening Mail for N rounds |
| `--go-inbox-timeout` | `6` | Force move on if stuck entering inbox for N rounds |

### RAG Analysis Configuration

The RAG analysis step uses environment variables for configuration:
- `API_BASE` - API base URL for LLM (default: `http://localhost:8003/v1`)
- `MODEL_NAME` - Model name for analysis (default: `Qwen3-VL-4B-Instruct`)
- `AGENT_TYPE` - Agent type: `OpenAIAgent` or `QwenVLAgent` (default: `OpenAIAgent`)

**Note**: The RAG system uses port 8003 by default, which is different from the GUI agent's port 8002. Make sure your LLM service is running on the correct port for each component.

## Step Mode (Micro-Instructions)

By default, the Mail pipeline uses **step mode**, which provides micro-instructions to the agent for each round. This approach:

- Reduces prompt complexity
- Improves action stability
- Better suited for local/weaker models

Each step focuses on a single action:
- "Find and tap the Mail app icon"
- "Navigate to the inbox/mail list"
- "Identify the top 5 emails"
- "Open the next unopened email"
- "Return to the mail list"

## Troubleshooting

### WebDriverAgent Connection Issues

**Problem**: Cannot connect to WDA

**Solutions**:
1. Verify WDA is running: `curl http://localhost:8100/status`
2. Check network connectivity or USB forwarding
3. Use `--wda-url` to specify the correct URL
4. For USB devices: `iproxy 8100 8100` then use `http://localhost:8100`

### Model API Issues

**Problem**: API calls fail or model not responding

**Solutions**:
1. Verify `API_BASE` and `MODEL_NAME` environment variables
2. Check that the LLM service is running on the correct port:
   - GUI agent uses port **8002** by default
   - RAG system uses port **8003** by default
3. Test API connectivity: `curl $API_BASE/health`
4. For local agents, ensure the service is listening on the correct port for each component
5. If using the combined script, make sure both services are running on their respective ports

### Screenshot Analysis Issues

**Problem**: RAG analysis fails or produces inaccurate results

**Solutions**:
1. Verify screenshot directory exists and contains PNG files
2. Check that screenshots are from email content views (not lists)
3. Ensure visual model is properly configured
4. Try limiting analysis with `--max-screenshots` for testing

### Task Execution Issues

**Problem**: Agent gets stuck or doesn't complete tasks

**Solutions**:
1. Increase `--max-rounds` if task needs more steps
2. Adjust `--max-no-progress-rounds` to allow earlier termination
3. Check timeout parameters (`--open-mail-timeout`, `--go-inbox-timeout`)
4. Review screenshots in `ios_logs/` to understand agent behavior

## Advanced Usage

### Using Different Models

```bash
export API_BASE='http://your-api-url/v1'
export MODEL_NAME='your-model-name'
export AGENT_TYPE='QwenVLAgent'

./run_mail_and_rag.sh
```

## Key Features

- **Vision-Language Integration**: Uses VLM agents to understand screenshots and make decisions
- **Automated Screenshot Capture**: Automatically captures screenshots during task execution
- **RAG-Based Analysis**: Analyzes captured screenshots to extract structured information
- **Step Mode**: Micro-instruction mode for improved stability with local models
- **Comprehensive Logging**: Detailed logs and traces for debugging and analysis

## Acknowledgments

This project references and draws inspiration from [Open-AutoGLM](https://github.com/zai-org/Open-AutoGLM), an open-source phone agent framework.

## License

See the main project LICENSE file.
