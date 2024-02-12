module.exports = {
  networks: {
    development: {
      host: "10.5.50.70",
      port: 7545,
      network_id: "*"
    },

    node1: {
      host: "10.5.50.70",
      port: 3334,            
      network_id: "1234",    
      websockets: true       
    },

    node2: {
      host: "10.5.50.71",
      port: 3335,            
      network_id: "1234",    
      websockets: true       
    },

  },
  compilers: {
    solc: {
      version: "0.5.0",   
    }
  },
};
