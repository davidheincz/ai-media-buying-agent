# AI-Driven Media Buying Agent - User Documentation

## Overview

The AI-Driven Media Buying Agent is a powerful tool that connects to Facebook Ads and Poe.com to automatically manage your advertising campaigns based on your media buying knowledge. The system learns from PDF documents you upload and applies this knowledge to optimize your campaigns for the best performance.

## Features

- **Document Processing**: Upload PDF documents containing your media buying knowledge
- **Facebook Ads Integration**: Connect to your Facebook Ads accounts
- **AI-Powered Decisions**: Automatic optimization based on your knowledge base
- **Hybrid Automation**: Choose which decisions require approval and which can be executed automatically
- **Performance Tracking**: Monitor campaign and ad set performance metrics
- **User-Friendly Interface**: Easy-to-use web application

## Getting Started

### 1. Registration and Login

1. Navigate to the web application URL provided by your administrator
2. Click "Register" to create a new account
3. Fill in your username, email, and password
4. Log in with your credentials

### 2. Connecting Facebook Ads Accounts

1. From the Dashboard, click "Connect Account" in the Facebook Ad Accounts section
2. You will be redirected to Facebook to authorize the application
3. Select the ad accounts you want to connect
4. After authorization, you will be redirected back to the dashboard with your accounts connected

### 3. Uploading Knowledge Documents

1. From the Dashboard or Documents page, click "Upload Document"
2. Enter a title for your document
3. Select a PDF file containing your media buying knowledge
4. Click "Upload"
5. The document will be processed in the background
6. You can monitor the processing status on the Documents page

### 4. Managing Campaigns

1. From the Dashboard, click "View Campaigns" next to an ad account
2. View all campaigns for the selected account
3. Create new campaigns using the "Create Campaign" button
4. Toggle campaigns on/off using the buttons in the Actions column
5. View ad sets for a campaign by clicking "View Ad Sets"

### 5. Managing Ad Sets

1. From the Campaigns page, click "View Ad Sets" for a campaign
2. View all ad sets for the selected campaign
3. Toggle ad sets on/off using the buttons in the Actions column
4. View performance metrics for each ad set

### 6. Reviewing AI Decisions

1. From the Dashboard or Decisions page, view pending AI decisions
2. For each decision, you can:
   - View details by clicking "Details"
   - Approve the decision by clicking "Approve"
   - Reject the decision by clicking "Reject"
3. View decision history to see previously approved or rejected decisions

### 7. Running Automation

1. From the Dashboard, click "Run Automation" next to an ad account
2. The AI will analyze your campaigns and ad sets based on your knowledge base
3. Decisions will be generated based on the automation level:
   - Autonomous: All decisions are executed automatically
   - Hybrid: Low-risk decisions are executed automatically, high-risk decisions require approval
   - Approval Required: All decisions require explicit approval

## Best Practices

### Document Preparation

For best results when uploading documents:

1. Include specific rules and thresholds in your documents
   - Example: "Decrease budget by 20% when CPA exceeds $10"
   - Example: "Pause ad sets with CTR below 1%"

2. Structure your documents with clear sections
   - Budget management rules
   - Ad set optimization strategies
   - Campaign creation guidelines
   - Performance thresholds

3. Include specific metrics and KPIs
   - CPA/CPL targets
   - CTR expectations
   - Conversion rate benchmarks

### Automation Settings

1. Start with "Approval Required" mode to review all AI decisions
2. As you gain confidence in the system, transition to "Hybrid" mode
3. Use "Autonomous" mode only for accounts with well-established rules and stable performance

### Regular Maintenance

1. Upload new documents as your strategies evolve
2. Review decision history regularly to understand AI behavior
3. Monitor campaign performance to ensure optimization is working as expected

## Troubleshooting

### Common Issues

1. **Document Processing Failed**
   - Ensure the document is a valid PDF
   - Check that the document is not password-protected
   - Try uploading a smaller document (under 10MB)

2. **Facebook Account Connection Failed**
   - Ensure you have admin access to the Facebook ad accounts
   - Check that your Facebook session is active
   - Try disconnecting and reconnecting the account

3. **AI Decisions Not Generating**
   - Ensure you have uploaded and processed at least one document
   - Check that your campaigns have sufficient performance data
   - Run automation manually from the Dashboard

### Support

If you encounter any issues not covered in this documentation, please contact your system administrator or support team.

## Security and Privacy

- All document data is stored securely and is only accessible to your account
- Facebook access tokens are encrypted in the database
- The system uses HTTPS for all communications
- User passwords are hashed and never stored in plain text

## System Requirements

- Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection
- Facebook Ads account with admin access
