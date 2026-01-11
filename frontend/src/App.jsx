import React, { useState, useRef } from 'react'
// Import the chat UI components (they must exist in ./components)
import ChatBox from './Components/ChatBox';
import MessageInput from './Components/MessageInput';
import ChatContainer from './Components/ChatContainer'; // optional styling for the chat layout

export default function App() {
  // ---- State & logic -------------------------------------------------
  const [messages, setMessages] = useState([]);
  const scrollRef = useRef(null);

  // Add a message to the list (user or bot)
  const addMessage = (text, isUser = true) => {
    const newMessage = { id: Date.now(), text, isUser };
    setMessages(prev => [...prev, newMessage]);

    // Auto‑scroll to the newest message
    if (scrollRef?.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  };

  // Simulated bot reply – replace with real LLM/API call later
  const handleUserMessage = (userText) => {
    addMessage(userText, true);
    const botReply = `You said: "${userText}" – processing...`;
    setTimeout(() => addMessage(botReply, false), 600);
  };
  // --------------------------------------------------------------------

  return (
    <div className="chat-container">
      {/* Message history (scrollable) */}
      <ChatBox messages={messages} ref={scrollRef} />

      {/* Input area for new messages */}
      <MessageInput onSend={handleUserMessage} />
    </div>
  );
}
