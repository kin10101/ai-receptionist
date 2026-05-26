# AI Voice Scheduling Receptionist

A conversational AI receptionist that simulates a real phone-based scheduling assistant for businesses.

The system handles inbound appointment conversations through natural multi-turn dialogue, enabling callers to:
- book appointments
- reschedule appointments
- cancel appointments
- confirm appointment details

It is designed to behave like a live front desk representative while maintaining strong workflow control through a stateful orchestration layer.

## Overview

This project demonstrates an operational AI receptionist built around:
- **stateful workflow orchestration (LangGraph v1)**
- **tool-driven scheduling execution**
- **Google ecosystem calendar and email integrations**
- **human handoff for escalations**
- **voice-ready architecture for future realtime telephony**

Users interact conversationally (rather than rigid forms). The agent gathers missing information, handles corrections, validates requests, executes scheduling tools, and keeps context across turns.

## Core Features

### 1) Multi-turn conversational scheduling
- Progressive slot-filling for appointment details
- Handles partial information and follow-up clarifications
- Supports caller preference changes mid-conversation
- Maintains conversational continuity across turns

### 2) Stateful workflow orchestration with LangGraph
- Intent detection and routing
- Shared conversation state and memory
- Tool invocation and response synthesis
- Structured control for completion, retries, and fallback paths

### 3) Google-integrated calendar management
The receptionist can perform real scheduling actions through Google services:
- check available time slots
- create calendar events
- modify existing appointments
- cancel bookings
- send confirmation emails
- generate invites

### 4) Google ADK-powered tool execution
- Secure, structured interaction with external services
- Extensible tool layer for scheduling and business workflows
- Foundation for future enterprise integrations

### 5) Human handoff and escalation
- Detects unsupported or conflict-heavy scenarios
- Supports explicit caller escalation requests
- Produces structured conversation summaries for live-agent transfer

### 6) Modular, voice-ready architecture
- Current implementation is text-based for reliable orchestration testing
- Architecture is prepared for speech pipelines:
  - speech-to-text (STT)
  - text-to-speech (TTS)
  - realtime voice call transport

## Example Interaction

**Customer:**
> Hi, I’d like to book an appointment for tomorrow afternoon.

**AI Receptionist:**
> Sure. What type of appointment would you like to schedule?

**Customer:**
> A consultation.

**AI Receptionist:**
> I found available consultation slots tomorrow at 2 PM and 4 PM. Which would you prefer?

**Customer:**
> 2 PM works.

**AI Receptionist:**
> Great. I’ve scheduled your consultation for tomorrow at 2 PM and sent a confirmation email to your registered address.

## Technical Stack

### Backend
- Python
- FastAPI
- LangGraph v1
- Google ADK
- Google Calendar API
- Gmail API

### Frontend
- Web-based mock call interface
- Realtime conversational chat simulation

## Future Integrations
- OpenAI Realtime API
- Twilio Voice
- Deepgram STT
- ElevenLabs or OpenAI TTS

## Project Goals

This repository is intended to showcase how agentic AI can automate real business operations with structured workflows and tool execution.

Key themes:
- conversational AI orchestration
- stateful agent workflows
- tool-driven decision systems
- enterprise workflow automation
- human-in-the-loop escalation
- real-world business integration patterns
