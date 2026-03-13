# Tenovice Fundraising Calculator

A simple fundraising web application for a small audience that allows supporters to submit pledges, see overall progress, and understand how their contribution influences the fundraising goal.

## Project purpose

This project supports fundraising for the **Tenovice** project.

The application is intended for a relatively small number of users:

- up to **1000 users**
- **infrequent access**
- low operational overhead
- low-cost infrastructure

The main goal is to provide a lightweight public-facing calculator where friends and supporters can enter their pledge, see the impact on total progress, and browse other anonymous pledges for inspiration.

---

## Business logic requirements

### Public user capabilities

The application should allow a user to:

- submit a pledge
- see the current fundraising progress
- see how their pledge changes the total
- browse all existing pledges for inspiration
- view only their own pledge as editable
- update only their own pledge later

### Visibility and privacy rules

- all pledges are visible publicly
- all pledges must remain **anonymous**
- a user must **not** be able to identify other users
- a user must only be able to view and edit **their own** pledge record in an editable way

This means the system should separate:

- **public pledge display data**  
  visible to everyone, but anonymous

from

- **private user ownership / update logic**  
  used only to let a user retrieve and modify their own pledge

---

## Proposed architecture

The current architecture idea is:

- **Static website hosted on Amazon S3**
- **AWS Lambda** for backend logic
- **Amazon API Gateway** for HTTP endpoints
- **Amazon DynamoDB** for pledge storage
- **AWS CDK** for infrastructure as code

This architecture fits the project well because it is:

- simple
- cost-efficient
- scalable enough for the expected traffic
- easy to maintain
- suitable for infrequent use

---

## High-level application flow

### 1. Public information page
The main page presents:

- project information
- fundraising purpose
- current financial / fundraising status
- link or call to action to participate

### 2. Fundraising calculator / pledge form
The pledge page allows a visitor to:

- enter a pledge
- immediately see how the pledge affects the overall target/progress
- submit the pledge
- browse other anonymous pledges

### 3. Returning user flow
A returning user should be able to:

- access their own pledge
- modify their pledge
- resubmit the updated amount

A returning user must not gain access to anyone else’s pledge.

---

## Core technical responsibilities

### Frontend
A static frontend hosted in **Amazon S3** should:

- render the public fundraising page
- display current totals and progress
- show anonymous pledges
- allow users to create or update their pledge
- provide a simple and intuitive calculator experience

### Backend
The backend built with **API Gateway + Lambda** should:

- accept new pledge submissions
- validate input
- store pledge records
- update existing pledge records
- return aggregated fundraising statistics
- return anonymous pledge lists for public display
- enforce the rule that users can access and update only their own pledge

### Data storage
**DynamoDB** should store:

- pledge records
- metadata needed for ownership / update access
- timestamps for creation and updates
- possibly precomputed or queryable summary values

---

## Suggested data model direction

A pledge record will likely need to contain two types of information:

### Public information
Data safe to show to everyone:

- anonymous pledge amount
- creation/update timestamp
- optional anonymous label if needed

### Private ownership information
Data used internally so a user can retrieve and update only their own pledge:

- user identifier
- edit token, login reference, or another ownership mechanism
- internal record ID

The public UI should never expose personally identifying information.

---

## Key design rule

The most important business rule in this project is:

**all pledges are public, but all identities are private**

So the system must support public transparency of contribution values while preserving anonymity and ensuring ownership-based editing rights.

---

## Why this stack

### S3
A static site is enough for the frontend and keeps hosting simple and cheap.

### Lambda + API Gateway
The backend logic is lightweight and event-driven, so serverless functions are a good fit.

### DynamoDB
The application needs simple storage for pledges and straightforward read/write access patterns.

### CDK
Infrastructure should be versioned together with the codebase and deployed reproducibly.

---

## Expected access patterns

The system mainly needs to support:

- create pledge
- update own pledge
- fetch fundraising totals
- fetch all anonymous pledges
- fetch own pledge
- calculate/display current progress

These access patterns are simple and well suited for a serverless design.

---

## Important implementation considerations

### Ownership model
The application needs a reliable way to ensure that a user can update only their own pledge.

Possible implementation approaches include:

- email-based identification
- token-based edit link
- lightweight authentication
- Cognito-based identity

This decision affects both UX and security.

### Anonymous public display
Even if all pledges are public, the displayed data should not reveal identity through:

- names
- emails
- direct identifiers
- overly revealing metadata

### Update flow
Updating a pledge should replace or amend the user’s existing pledge without creating confusion in totals or duplicate visible ownership.

---

## Repository structure idea

```text
project/
├── cdk/                # AWS CDK infrastructure
├── frontend/           # static website
├── backend/            # Lambda handlers
├── docs/               # architecture notes and diagrams
└── README.md