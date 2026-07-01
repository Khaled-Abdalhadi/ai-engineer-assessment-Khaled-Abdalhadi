import './App.css'
import {ChatBox} from "@mui/x-chat";
import type { ChatAdapter, ChatMessage } from '@mui/x-chat/headless';

function App() {

  //backend server URL (DO NOT CHANGE PROD domain, only change local domain based on where your server is hosted locally)
  const hostName = import.meta.env.PROD ? 'https://ai-engineer-assessment-khaled-abdalhadi.onrender.com/' : 'http://127.0.0.1:8000'

  const initialConversations = [
    {
      id: "demo-conversation",
      participants: [
        {
          displayName: 'user (test)',
          id: 'user-1',
          role: 'user' as const,
          avatatUrl: 'https://img.magnific.com/premium-vector/portrait-young-arab-man-with-beard-middle-eastern-ethnicity-businessman-flat-illustration_1224831-38.jpg?semt=ais_hybrid&w=740&q=80'
      
        },
        {
          displayName: 'AI assistant (test)',
          id: 'assistant-1',
          role: 'assistant' as const,
          avatarUrl: 'https://img.magnific.com/premium-vector/portrait-young-arab-man-with-beard-middle-eastern-ethnicity-businessman-flat-illustration_1224831-38.jpg?semt=ais_hybrid&w=740&q=80'
        }
      ]
    }
  ]

  const minimalMessages: ChatMessage[] = [
    {
      id: 'starter-msg-1',
      conversationId: 'demo-conversation',
      role: 'assistant',
      author: {
        id: 'assistant-1',
        displayName: 'AI assistant (test)',
        role: 'assistant'
      },
      parts: [{type: 'text' as const, text: "Hello! I am your AI chatbot  \u{1F916}\n\nI am happy to answer you with any questions regarding superheros \u{1F9B8} or the FIFA world cup \u{26BD}\n\nHow may I help you? \u{1F60A}"}],

    }
  ]

  //since the current backend sends a non-streaming response we have to implment an adapter with "fake" streaming
  //code snippet from: https://mui.com/x/react-chat/backend/building-an-adapter/
  const adapter: ChatAdapter = {
    async sendMessage({ message, signal }) {
      return new ReadableStream({
        async start(controller) {
          const response = await fetch(`${hostName}/ask`, {
            method: 'POST',
            body: JSON.stringify(
              message.parts[0]?.type === 'text' ? message.parts[0].text : '',
            ),
            signal,
          });
  
          const reader = response.body!.getReader();
          const decoder = new TextDecoder();
          const messageId = `msg-${Date.now()}`;
  
          controller.enqueue({ type: 'start', messageId });
          controller.enqueue({ type: 'text-start', id: 'text-1' });
  
          try {
            while (true) {
              var finalMessage = "";
              const { done, value } = await reader.read();
              if (done) break;

              const text = JSON.parse(decoder.decode(value, { stream: true }));
           
              //can't find the super hero
              if(text.message == `I am sorry but I could not find any information about ${text.name}  😕`|| text.message == "Your message is too long, please send a shorter message!") {
                finalMessage = text.message
              }

              //either superhero or world cup is called
              else if(typeof text == "object") {
                const modelMessage = text.message;
                const source = text.source;
                const source_url = text.source_url;

                if(source == "superhero API") {
                  const superHeroName  = text.name;
                  const superHero_data = JSON.parse(modelMessage);
                  const biography = superHero_data.summary;
                  const image_url = superHero_data.image_url;

                  finalMessage = `${biography}\n\n**source:** [${source}](${source_url})`
                  
                  //add superHero image to response
                  controller.enqueue({
                    type: 'file',
                    id: `img-${Date.now()}`,
                    mediaType: 'image/jpeg',
                    url: `${image_url}`,
                    filename: `show a picture of ${superHeroName}`
                  });
                }

                else {
                  finalMessage = `${modelMessage}\n\n\n**source:** [${source}](${source_url})`
                }
          
              }
              
              //response for unrelated queries that the model isn't supposed to answer
              else {
                finalMessage = text
              }
     
            
              controller.enqueue({ type: 'text-delta', id: 'text-1', delta: finalMessage });
            }
            controller.enqueue({ type: 'text-end', id: 'text-1' });
            controller.enqueue({ type: 'finish', messageId });
          } catch (error) {
            controller.enqueue({ type: 'text-end', id: 'text-1' });
            controller.enqueue({ type: 'abort', messageId });
          } finally {
            controller.close();
          }
        },
      });
    },
  };


  return (
    <>
      <ChatBox
        initialActiveConversationId='demo-conversation'
        initialConversations={initialConversations}
        initialMessages={minimalMessages}
        density = 'comfortable'
        adapter = {adapter}
        features = {{
          attachments: false,
          conversationHeader: false,
        }}
        sx = {{
          height: 800,
          border:'1px solid',
          borderColor: 'divider',
          borderRadius: 1,

          "& .MuiChatMessage-bubble p": {
            marginBottom: "12px"
          },

          "& .MuiChatMessage-filePreview": {
            display: "none"
          }
        }}
        slotProps={{
          messageContent: {
            style: {
              textAlign: "left",
            }
          },
          messageAuthorName: (ownerState) => ({
            style: {
              textAlign: ownerState.authorRole === "assistant" ? "left" : "right",
              whiteSpace: "pre-wrap"
            }
          }),
        }}
      />

    </>
  )
}

export default App
