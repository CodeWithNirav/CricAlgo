# CricAlgo Telegram Bot - User Guide

## Overview

The CricAlgo Telegram Bot is your gateway to cricket algorithm trading contests. This comprehensive guide explains all the features and functionality available to users through the Telegram interface.

## Getting Started

### 1. Registration & Login
- **Command**: `/start [invite_code]`
- **Description**: Register a new account or login to existing account
- **Optional**: Include an invite code to receive a 5 USDT bonus
- **Features**:
  - Automatic account creation
  - Wallet setup
  - Invite code validation with bonus crediting
  - Chat mapping for notifications

### 2. Main Menu
- **Command**: `/menu`
- **Description**: Access the main navigation menu
- **Features**:
  - Quick access to all bot functions
  - Intuitive button-based navigation
  - Always available from any screen

## Core Features

### 💰 Balance Management

#### Check Balance
- **Command**: `/balance`
- **Features**:
  - View deposit balance
  - View winning balance  
  - View bonus balance
  - See total available balance
  - Quick deposit button

#### Deposit Funds
- **Command**: `/deposit`
- **Features**:
  - Per-user unique deposit addresses
  - Unique deposit reference (memo) for each transaction
  - Step-by-step deposit instructions
  - Minimum deposit: No minimum
  - Network: BEP20 (BSC)
  - Automatic balance updates
  - Deposit confirmation notifications
  - "Notify me when confirmed" subscription

#### Withdraw Funds
- **Command**: `/withdraw`
- **Features**:
  - Quick amount options ($10, $25, $50, $100)
  - Custom amount input
  - Address validation
  - Withdrawal request creation
  - Status tracking
  - Request cancellation
  - Admin approval workflow
  - Automatic notifications on status changes

### 🏏 Contest Participation

#### View Available Contests
- **Command**: `/contests`
- **Features**:
  - List of all open contests
  - Contest details (title, entry fee, prize structure, player count)
  - Real-time player count
  - Contest status information
  - Join contest functionality
  - View contest details

#### Join Contests
- **Features**:
  - One-click contest joining
  - Automatic balance checking
  - Entry fee deduction
  - Idempotent operations (prevents duplicate entries)
  - Success confirmation
  - Entry ID generation

#### My Contests
- **Command**: Access via main menu
- **Features**:
  - View all your contest entries
  - Entry details and status
  - Contest information
  - Join date tracking
  - Position and prize information (after settlement)

#### Contest Details
- **Features**:
  - Detailed contest information
  - Prize structure breakdown
  - Player count and limits
  - Start time and status
  - Rules and descriptions
  - Join/View entry options

### 📊 Account Management

#### Settings
- **Features**:
  - View account information
  - Username and user ID display
  - Account status
  - Member since date
  - Notification preferences
  - Profile management

#### Support
- **Features**:
  - Contact information
  - Common issues and solutions
  - Help resources
  - Support channels
  - Troubleshooting tips

## Advanced Features

### 🔔 Notifications
- **Deposit Confirmations**: Automatic notifications when deposits are confirmed
- **Withdrawal Updates**: Status changes for withdrawal requests
- **Contest Settlements**: Notifications when contests are settled
- **Prize Notifications**: Winner and participant notifications
- **Balance Updates**: Real-time balance change notifications

### 🎁 Invite System
- **Invite Code Usage**: Use invite codes during registration for bonuses
- **Bonus Crediting**: Automatic 5 USDT bonus for valid invite codes
- **Retry Mechanism**: Option to retry with invalid codes
- **Code Validation**: Real-time invite code validation

### 🔒 Security Features
- **Idempotent Operations**: Prevents duplicate actions
- **Rate Limiting**: Prevents spam and abuse
- **Input Validation**: All user inputs are validated
- **Secure Transactions**: All financial operations are secure
- **Chat Mapping**: Persistent chat ID storage for notifications

## User Interface

### Inline Keyboards
- **Main Menu**: Quick access to all features
- **Balance**: Check balance and deposit options
- **Contests**: View and join contests
- **Withdrawals**: Manage withdrawal requests
- **Settings**: Account and preference management
- **Support**: Help and contact options

### Interactive Elements
- **Quick Amount Buttons**: Pre-defined withdrawal amounts
- **Status Tracking**: Real-time status updates
- **Navigation**: Easy movement between features
- **Error Handling**: User-friendly error messages
- **Confirmation Dialogs**: Clear action confirmations

## Commands Reference

### User Commands
- `/start [code]` - Register or login (optional invite code)
- `/menu` - Show main menu
- `/balance` - Check wallet balance
- `/deposit` - Get deposit instructions
- `/contests` - View available contests
- `/withdraw` - Request withdrawal
- `/help` - Show available commands

### Admin Commands (Admin Only)
- `/create_contest` - Create a new contest
- `/settle` - Settle a contest
- `/approve_withdraw` - Approve user withdrawal
- `/admin_help` - Show admin commands

## User Experience Features

### 🚀 Quick Actions
- **One-Click Operations**: Most actions require single button press
- **Smart Defaults**: Pre-filled options for common actions
- **Context-Aware**: Interface adapts to user's current state
- **Progressive Disclosure**: Information revealed as needed

### 💡 Pro Tips
- Use inline buttons for quick actions
- Check your balance before joining contests
- Contact support if you need help
- Use `/menu` for easy navigation
- Subscribe to deposit notifications for real-time updates

### 🔄 Error Handling
- **Graceful Degradation**: System continues working even with errors
- **User-Friendly Messages**: Clear error explanations
- **Retry Options**: Easy recovery from errors
- **Support Integration**: Direct access to help when needed

## Technical Features

### 🏗️ Architecture
- **Async Operations**: Fast, non-blocking operations
- **Database Transactions**: Secure financial operations
- **Redis Caching**: Fast response times
- **Idempotency**: Prevents duplicate operations
- **Rate Limiting**: Prevents abuse

### 📱 Mobile Optimized
- **Telegram Integration**: Native Telegram interface
- **Mobile-First Design**: Optimized for mobile devices
- **Touch-Friendly**: Large, easy-to-tap buttons
- **Responsive Layout**: Adapts to different screen sizes

## Getting Help

### Support Channels
- **Email**: support@cricalgo.com
- **Telegram**: @CricAlgoSupport
- **Website**: https://cricalgo.com/support
- **In-Bot Support**: Use the support button in the bot

### Common Issues
- **Balance not updating**: Wait for blockchain confirmation
- **Can't join contest**: Check your balance and contest status
- **Withdrawal issues**: Contact support with your user ID
- **Technical problems**: Use the support system for assistance

## Best Practices

### 💰 Financial Management
- Always check your balance before joining contests
- Keep track of your deposits and withdrawals
- Use the notification system for real-time updates
- Contact support for any financial concerns

### 🏏 Contest Participation
- Read contest details before joining
- Understand the prize structure
- Check contest status and player limits
- Monitor your contest entries

### 🔒 Security
- Never share your private keys or passwords
- Use only official CricAlgo channels
- Report any suspicious activity
- Keep your Telegram account secure

## Conclusion

The CricAlgo Telegram Bot provides a comprehensive, user-friendly interface for all your cricket algorithm trading contest needs. With features like real-time notifications, secure transactions, and intuitive navigation, it's designed to make your trading experience smooth and enjoyable.

For additional support or questions, use the in-bot support system or contact our support team directly.

---

*This guide covers all user-facing features of the CricAlgo Telegram Bot. For technical documentation or developer information, please refer to the technical documentation files.*
